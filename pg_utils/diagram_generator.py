import os
import re


def get_all_files_in_directory(directory: str) -> list[str]:
    """Recursively retrieves all files in a directory."""
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files


def format_column_constraints(constraints: str) -> str:
    """Formats SQL column constraints to dbdiagram.io format."""
    constraints = re.sub(r"\bPRIMARY KEY\b", "PK", constraints)
    constraints = re.sub(r"\bDEFAULT\b", "DEFAULT:", constraints)

    constraint_elements = re.split(r"\s+", constraints)
    formatted_constraints = ", ".join(constraint_elements)

    formatted_constraints = formatted_constraints.replace("NOT,", "NOT").replace(
        "DEFAULT:,", "DEFAULT:"
    )
    formatted_constraints = re.sub(
        r"DEFAULT:\s?([^\s,]+)", r'DEFAULT: "\1"', formatted_constraints
    )

    return f"[{formatted_constraints}]"


def parse_foreign_key_reference(line: str, table_name: str) -> str:
    """Parses a foreign key reference from an SQL line to dbdiagram.io format."""
    fk_match = re.search(
        r'CONSTRAINT "([\w]+)" FOREIGN KEY \("([\w]+)"\) REFERENCES "([\w]+)" \("([\w]+)"\)'
        r"( ON DELETE (CASCADE|SET NULL|RESTRICT|NO ACTION))?"
        r"( ON UPDATE (CASCADE|SET NULL|RESTRICT|NO ACTION))?",
        line,
    )

    if fk_match:
        _, column_name, ref_table, ref_column, _, delete_action, _, update_action = (
            fk_match.groups()
        )
        return f"Ref: {table_name}.{column_name} > {ref_table}.{ref_column} [DELETE: {delete_action}, UPDATE: {update_action}]\n"
    return ""


def parse_sql_to_dbdiagram_format(file_content: str) -> str:
    """Parses SQL CREATE TABLE statements to dbdiagram.io format."""
    create_table_regex = re.compile(
        r'CREATE TABLE "([\w]+)" \(([\s\S]*?)\);', re.MULTILINE
    )
    result = []
    references_section = []

    for match in create_table_regex.finditer(file_content):
        table_name = match.group(1)
        column_definitions = match.group(2).strip().split(",\n")
        indexes = []

        formatted_columns = []
        for line in column_definitions:
            line = line.strip()

            # Primary Key Constraint
            if "CONSTRAINT" in line and "_pkey" in line:
                pk_match = re.search(
                    r'CONSTRAINT "([\w]+)" PRIMARY KEY \(([\w",\s]+)\)', line
                )
                if pk_match:
                    pk_columns = (
                        pk_match.group(2).replace('"', "").replace(" ", "").split(",")
                    )
                    indexes.append(
                        f'  indexes {{\n    ({", ".join(pk_columns)}) [pk]\n  }}'
                    )
                continue

            # Unique Constraint
            if "CONSTRAINT" in line and "UNIQUE" in line:
                unique_match = re.search(
                    r'CONSTRAINT "([\w]+)" UNIQUE \(([\w",\s]+)\)', line
                )
                if unique_match:
                    unique_columns = (
                        unique_match.group(2)
                        .replace('"', "")
                        .replace(" ", "")
                        .split(",")
                    )
                    indexes.append(
                        f'  indexes {{\n    ({", ".join(unique_columns)}) [unique]\n  }}'
                    )
                continue

            # Foreign Key Constraint
            if "CONSTRAINT" in line and "_fkey" in line:
                references_section.append(parse_foreign_key_reference(line, table_name))
                continue

            parts = line.split()
            column_name = parts[0].replace('"', "")
            column_type = parts[1].replace('"', "")
            constraints = format_column_constraints(
                " ".join(parts[2:]).replace('"', "")
            )

            formatted_columns.append(f'  "{column_name}" {column_type} {constraints}')

        table_definition = (
            f"Table {table_name} {{\n"
            + "\n".join(formatted_columns)
            + ("\n" + "\n".join(indexes) if indexes else "")
            + "\n}"
        )
        result.append(table_definition)

    return "\n\n".join(result + references_section).strip()


def generate_db_diagram_file(migrations_directory_path: str, diagram_output_file: str):
    """Generates a dbdiagram.io compatible file from SQL migration files."""
    try:
        migration_files = get_all_files_in_directory(migrations_directory_path)

        file_contents = [
            open(file, "r", encoding="utf-8").read() for file in migration_files
        ]
        db_diagram_content = "\n\n".join(
            filter(bool, map(parse_sql_to_dbdiagram_format, file_contents))
        )

        with open(diagram_output_file, "w", encoding="utf-8") as output_file:
            output_file.write(db_diagram_content.strip())

        print(
            f"Arquivo {diagram_output_file} gerado com sucesso no formato dbdiagram.io!"
        )
    except Exception as error:
        print(f"Erro ao gerar o arquivo dbdiagram: {error}")
