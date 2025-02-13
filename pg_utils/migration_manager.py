import os
from .database import Database


class MigrationManager:
    def __init__(self, migrations_path: str, db: Database):
        self.migrations_path = migrations_path
        self.db = db

    def initialize(self):
        """Inicializa o banco de dados e cria a tabela de controle de migrações."""
        self.db.connect()
        self.db.execute_query(
            """
            CREATE TABLE IF NOT EXISTS "_migrations" (
                "id" SERIAL PRIMARY KEY,
                "name" TEXT NOT NULL,
                "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        )

    def get_applied_migrations(self) -> list[str]:
        """Retorna uma lista de migrações já aplicadas no banco."""
        result = self.db.find_many("_migrations", select={"name": True})
        return [row["name"] for row in result]

    def apply_migration(self, file_name: str, direction: str):
        """Aplica ou reverte uma migração específica."""
        file_path = os.path.join(self.migrations_path, file_name)

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                file_content = file.read()

            up_sql, down_sql = file_content.split("-- down")
            sql_to_execute = (
                up_sql.replace("-- up", "") if direction == "up" else down_sql
            )

            self.db.execute_query("BEGIN")
            self.db.execute_query(sql_to_execute)

            if direction == "up":
                self.db.insert_into_table("_migrations", {"name": file_name})
            else:
                self.db.delete_from_table("_migrations", {"name": file_name})

            self.db.execute_query("COMMIT")
            print(f'Migração "{file_name}" ({direction}) aplicada com sucesso!')

        except Exception as err:
            print(f'Erro ao aplicar migração "{file_name}" ({direction}):', err)
            self.db.execute_query("ROLLBACK")
            raise

    def apply_all_migrations(self):
        """Aplica todas as migrações pendentes."""
        applied_migrations = self.get_applied_migrations()
        all_migrations = sorted(os.listdir(self.migrations_path))
        pending_migrations = [m for m in all_migrations if m not in applied_migrations]

        if not pending_migrations:
            print("Nenhuma migração pendente encontrada.")
            return

        for migration in pending_migrations:
            print(f"Aplicando migração: {migration}")
            self.apply_migration(migration, "up")

        print("Todas as migrações foram aplicadas com sucesso!")

    def revert_last_migration(self):
        """Reverte a última migração aplicada."""
        result = self.db.find_first(
            "_migrations", select={"name": True}, order_by={"id": "DESC"}
        )
        last_migration = result["name"] if result else None

        if not last_migration:
            print("Nenhuma migração encontrada para reverter.")
            return

        print(f"Revertendo a migração: {last_migration}")
        self.apply_migration(last_migration, "down")
        print(f'Migração "{last_migration}" revertida com sucesso!')

    def revert_all_migrations(self):
        """Reverte todas as migrações aplicadas, na ordem inversa."""
        results = self.db.find_many(
            "_migrations", select={"name": True}, order_by={"id": "DESC"}
        )

        if not results:
            print("Nenhuma migração encontrada para reverter.")
            return

        print("Iniciando a reversão de todas as migrações...")
        for migration in results:
            print(f"Revertendo a migração: {migration['name']}")
            self.apply_migration(migration["name"], "down")
            print(f'Migração "{migration["name"]}" revertida com sucesso!')

        print("Todas as migrações foram revertidas com sucesso!")
