import os
from datetime import datetime


class MigrationCreate:
    def __init__(self, migrations_path: str):
        self.migrations_path = migrations_path

    def create_migration_file(self, name: str):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S") + str(
            int(datetime.now().microsecond / 1000)
        ).zfill(3)
        file_name = f"{timestamp}_{name.replace(' ', '_')}.sql"
        file_path = os.path.join(self.migrations_path, file_name)

        file_content = "-- up\n\n-- down\n"

        try:
            with open(file_path, "w") as file:
                file.write(file_content)
            print(f"Migração criada com sucesso: {file_path}")
        except Exception as err:
            print(f"Erro ao criar a migração: {err}")
