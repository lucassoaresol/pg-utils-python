import json
import psycopg
from psycopg import sql

from typing import Any, Dict, List, Literal, Optional, Tuple
from .database_types import JoinParams, WhereClause, WhereCondition


class Database:
    def __init__(self, user: str, host: str, password: str, port: int, database: str):
        self.user = user
        self.host = host
        self.password = password
        self.port = port
        self.database = database

    def connect(self):
        self.connection = psycopg.connect(
            dbname=self.database,
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            autocommit=False,
        )

    def build_where_clause(
        self,
        where: Optional[WhereClause] = None,
        values: Optional[List[Any]] = None,
        main_table_alias: Optional[str] = None,
    ) -> Tuple[str, List[Any]]:
        if not where:
            return "", []

        and_conditions = []
        or_conditions = []
        where_values = values.copy() if values else []

        def format_condition(expression: str, is_not: bool) -> str:
            if is_not:
                return f"NOT ({expression})"
            return expression

        def parse_simple_comparison(
            column: str, value: Any, is_not: bool, conditions_array: List[str]
        ):
            if value is None:
                conditions_array.append(format_condition(f"{column} IS NULL", is_not))
            elif isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                conditions_array.append(
                    format_condition(f"{column} IN ({placeholders})", is_not)
                )
                where_values.extend(value)
            else:
                conditions_array.append(format_condition(f"{column} = %s", is_not))
                where_values.append(value)

        def parse_mode_comparison(
            column: str, condition: Dict[str, Any], conditions_array: List[str]
        ):
            mode = condition.get("mode")
            value = condition.get("value")
            is_not = condition.get("is_not", False)

            if mode == "ilike":
                conditions_array.append(format_condition(f"{column} ILIKE %s", is_not))
                where_values.append(f"%{value}%")
            elif mode == "like":
                conditions_array.append(format_condition(f"{column} LIKE %s", is_not))
                where_values.append(f"%{value}%")
            elif mode == "date":
                conditions_array.append(
                    format_condition(f"DATE({column}) = %s", is_not)
                )
                where_values.append(value)
            else:
                parse_simple_comparison(column, value, is_not, conditions_array)

        def parse_range_operators(
            column: str, condition: Dict[str, Any], conditions_array: List[str]
        ):
            for op_key, sql_op in [
                ("lt", "<"),
                ("lte", "<="),
                ("gt", ">"),
                ("gte", ">="),
            ]:
                if op_key in condition:
                    cond_value = condition[op_key]
                    is_not = False

                    if isinstance(cond_value, dict):
                        value = cond_value.get("value")
                        is_not = cond_value.get("is_not", False)
                    else:
                        value = cond_value

                    conditions_array.append(
                        format_condition(f"{column} {sql_op} %s", is_not)
                    )
                    where_values.append(value)

        def process_condition(
            key: str,
            condition: WhereCondition,
            conditions_array: List[str],
            alias: Optional[str] = None,
        ):
            column = f"{alias}.{key}" if alias and "." not in key else key

            if condition is None:
                conditions_array.append(f"{column} IS NULL")
            elif isinstance(condition, dict):
                if "value" in condition:
                    parse_mode_comparison(column, condition, conditions_array)
                elif any(op in condition for op in ("lt", "lte", "gt", "gte")):
                    parse_range_operators(column, condition, conditions_array)
            else:
                parse_simple_comparison(column, condition, False, conditions_array)

        for key, condition in where.items():
            if key != "OR":
                process_condition(key, condition, and_conditions, main_table_alias)

        if "OR" in where:
            for key, condition in where["OR"].items():
                process_condition(key, condition, or_conditions, main_table_alias)

        clause = ""
        if and_conditions or or_conditions:
            clause += " WHERE "
            if and_conditions:
                clause += f"({' AND '.join(and_conditions)})"
            if or_conditions:
                if and_conditions:
                    clause += " OR "
                clause += f"({' OR '.join(or_conditions)})"

        return clause, where_values

    def create_alias(self, table: str, existing_aliases: set) -> str:
        table = table.lstrip("_")
        parts = table.split("_")
        alias = "".join(part[0] for part in parts)
        counter = 0

        while alias in existing_aliases:
            counter += 1
            alias = "".join(part[0] for part in parts) + str(counter)

        existing_aliases.add(alias)

        return alias

    def execute_query(
        self, query: str, params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            if not cursor.description:
                self.connection.commit()
                return None
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results

    def create_database(self):
        with psycopg.connect(
            dbname="postgres",
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            autocommit=True,
        ) as client:
            with client.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (self.database,)
                )
                exists = cursor.fetchone()
                if exists:
                    print(f'Banco de dados "{self.database}" já existe.')
                else:
                    cursor.execute(f'CREATE DATABASE "{self.database}"')
                    print(f'Banco de dados "{self.database}" criado com sucesso.')

    def insert_into_table(
        self,
        table: str,
        data_dict: Dict[str, Any],
        select: Optional[Dict[str, bool]] = None,
    ) -> Any:
        columns = [col for col in data_dict.keys() if data_dict[col] is not None]
        values = [
            (
                json.dumps(data_dict[col])
                if isinstance(data_dict[col], dict)
                else data_dict[col]
            )
            for col in columns
        ]

        if select:
            selected_fields = [col for col, include in select.items() if include]
            returning_clause = sql.SQL("RETURNING {}").format(
                sql.SQL(", ").join(map(sql.Identifier, selected_fields))
            )
        else:
            returning_clause = sql.SQL("")

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) {}").format(
            sql.Identifier(table),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(values)),
            returning_clause,
        )

        with self.connection.cursor() as cursor:
            cursor.execute(insert_query, values)
            result = cursor.fetchone() if select else None
            self.connection.commit()

        if result and select:
            return dict(zip(selected_fields, result))

        return None

    def insert_many_into_table(
        self,
        table: str,
        data_list: List[Dict[str, Any]],
    ) -> Any:
        columns = [col for col in data_list[0].keys()]
        values = [
            [
                (
                    json.dumps(record[col])
                    if isinstance(record[col], dict)
                    else record[col]
                )
                for col in columns
            ]
            for record in data_list
        ]

        placeholders = sql.SQL(", ").join(
            sql.SQL("({})").format(
                sql.SQL(", ").join(sql.Placeholder() for _ in columns)
            )
            for _ in values
        )

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES {}").format(
            sql.Identifier(table),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            placeholders,
        )

        flattened_values = [item for sublist in values for item in sublist]

        with self.connection.cursor() as cursor:
            cursor.execute(insert_query, flattened_values)
            self.connection.commit()

        return None

    def update_into_table(
        self,
        table: str,
        data_dict: Dict[str, Any],
        where: Optional[WhereClause] = None,
    ) -> None:
        columns = data_dict.keys()
        values = [data_dict[col] for col in columns]

        set_clause = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(col)) for col in columns
        )

        where_clause, where_values = self.build_where_clause(where, values)

        query = sql.SQL("UPDATE {} SET {}{}").format(
            sql.Identifier(table), set_clause, sql.SQL(where_clause)
        )

        with self.connection.cursor() as cursor:
            cursor.execute(query, where_values)
            self.connection.commit()

    def delete_from_table(
        self, table: str, where: Optional[WhereClause] = None
    ) -> None:
        where_clause, where_values = self.build_where_clause(where)

        query = sql.SQL("DELETE FROM {} {}").format(
            sql.Identifier(table), sql.SQL(where_clause)
        )

        with self.connection.cursor() as cursor:
            cursor.execute(query, where_values)
            self.connection.commit()

    def find_many(
        self,
        table: str,
        alias: Optional[str] = None,
        order_by: Optional[Dict[str, Literal["ASC", "DESC"]]] = None,
        select: Optional[Dict[str, bool]] = None,
        where: Optional[WhereClause] = None,
        joins: Optional[JoinParams] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        group_by: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        query_aux = ""
        selected_fields = []
        existing_aliases = set()

        main_table_alias = alias or self.create_alias(table, existing_aliases)
        if alias:
            existing_aliases.add(alias)

        if select and len(select) > 0:
            for key, is_selected in select.items():
                if is_selected:
                    if " AS " in key:
                        original_key, alias = key.split(" AS ")
                        if "." not in original_key:
                            selected_fields.append(
                                f"{main_table_alias}.{original_key} AS {alias}"
                            )
                        else:
                            selected_fields.append(f"{original_key} AS {alias}")
                    elif "*" in key:
                        if "." not in key:
                            selected_fields.append(f"{main_table_alias}.{key}")
                    else:
                        if "." not in key:
                            selected_fields.append(f"{main_table_alias}.{key}")
                        else:
                            sl_split = key.split(".")
                            sl_alias = sl_split[0]
                            column_name = sl_split[-1]
                            if sl_alias != main_table_alias:
                                selected_fields.append(
                                    f"{key} AS {sl_alias}_{column_name}"
                                )
                            else:
                                selected_fields.append(key)
        else:
            selected_fields.append(f"{main_table_alias}.*")

        if joins:
            for join in joins:
                join_alias = join.get("alias") or self.create_alias(
                    join["table"], existing_aliases
                )

                if "alias" in join:
                    existing_aliases.add(join["alias"])

                join_type = join.get("type", "INNER")

                if select and len(select) > 0:
                    for key, is_selected in select.items():
                        if is_selected:
                            if "*" in key:
                                if "." in key:
                                    sl_split = key.split(".")
                                    sl_alias = sl_split[0]
                                    if sl_alias == join_alias:
                                        join_columns = self.find_many(
                                            "information_schema.columns",
                                            "i",
                                            where={"table_name": join["table"]},
                                            select={"column_name": True},
                                        )
                                        selected_fields.extend(
                                            f"{join_alias}.{column['column_name']} AS {join_alias}_{column['column_name']}"
                                            for column in join_columns
                                        )

                else:
                    join_columns = self.find_many(
                        "information_schema.columns",
                        "i",
                        where={"table_name": join["table"]},
                        select={"column_name": True},
                    )
                    selected_fields.extend(
                        f"{join_alias}.{column['column_name']} AS {join_alias}_{column['column_name']}"
                        for column in join_columns
                    )

                join_conditions = " AND ".join(
                    f"{column} = {join_alias}.{value}"
                    for key, value in join["on"].items()
                    for column in [key if "." in key else f"{main_table_alias}.{key}"]
                )

                query_aux += f" {join_type} JOIN {join['table']} AS {join_alias} ON {join_conditions}"

        where_clause, where_values = self.build_where_clause(
            where, main_table_alias=main_table_alias
        )

        group_clause = ""
        if group_by:
            group_clause = "GROUP BY " + ", ".join(
                (f"{main_table_alias}.{key}" if "." not in key else key)
            )

        order_clause = ""
        if order_by:
            order_clause = "ORDER BY " + ", ".join(
                (
                    f"{main_table_alias}.{field} {direction}"
                    if "." not in field
                    else f"{field} {direction}"
                )
                for field, direction in order_by.items()
            )

        limit_clause = f"LIMIT {limit}" if limit is not None else ""

        offset_clause = f"OFFSET {offset}" if offset is not None else ""

        query = (
            f"SELECT {', '.join(selected_fields)} FROM {table} AS {main_table_alias} "
            + query_aux
            + f" {where_clause} {group_clause} {order_clause} {limit_clause} {offset_clause};"
        )

        return self.execute_query(query, where_values)

    def find_first(
        self,
        table: str,
        alias: Optional[str] = None,
        order_by: Optional[Dict[str, Literal["ASC", "DESC"]]] = None,
        select: Optional[Dict[str, bool]] = None,
        where: Optional[WhereClause] = None,
        joins: Optional[JoinParams] = None,
    ) -> Optional[Dict[str, Any]]:
        result = self.find_many(table, alias, order_by, select, where, joins, 1)
        return result[0] if result else None

    def count(
        self,
        table: str,
        alias: Optional[str] = None,
        where: Optional[WhereClause] = None,
        joins: Optional[JoinParams] = None,
    ) -> int:
        query_aux = ""
        existing_aliases = set()

        main_table_alias = alias or self.create_alias(table, existing_aliases)
        if alias:
            existing_aliases.add(alias)

        if joins:
            for join in joins:
                join_alias = join.get("alias") or self.create_alias(
                    join["table"], existing_aliases
                )

                if "alias" in join:
                    existing_aliases.add(join["alias"])

                join_type = join.get("type", "INNER")

                join_conditions = " AND ".join(
                    f"{column} = {join_alias}.{value}"
                    for key, value in join["on"].items()
                    for column in [key if "." in key else f"{main_table_alias}.{key}"]
                )

                query_aux += f" {join_type} JOIN {join['table']} AS {join_alias} ON {join_conditions}"

        where_clause, where_values = self.build_where_clause(
            where, main_table_alias=main_table_alias
        )

        query = (
            f"SELECT COUNT(*) AS total FROM {table} AS {main_table_alias} "
            + query_aux
            + f" {where_clause};"
        )

        result = self.execute_query(query, where_values)

        return result[0]["total"] if result else 0

    def close(self):
        self.connection.close()
