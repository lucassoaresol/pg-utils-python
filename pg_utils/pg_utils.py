from .database import Database
from .migration_manager import MigrationManager


class PgUtils:

    def __init__(
        self,
        user: str,
        host: str,
        password: str,
        port: int,
        database: str,
        migrations_path: str,
        manage_migrations: bool,
    ):
        self.database = database
        self.manage_migrations = manage_migrations
        self.db_instance = Database(user, host, password, port, self.database)
        self.migrations = MigrationManager(migrations_path, self.db_instance)

    def create_and_connect_database(self):
        if not self.manage_migrations:
            raise Exception(
                "O gerenciamento de migrações não está ativado. A criação do banco de dados não é permitida."
            )

        try:
            self.db_instance.create_database()
            print(f'Banco de dados "{self.database}" criado e pool inicializado.')
        except Exception as err:
            print("Erro ao criar o banco de dados:", err)

    def get_client_database(self):
        return self.db_instance

    def get_manage_migrations(self):
        return self.manage_migrations

    def get_migrations(self):
        if self.manage_migrations:
            try:
                self.migrations.initialize()
                print("Gerenciamento de migrações iniciado.")
                return self.migrations
            except Exception as err:
                print("Erro ao inicializar migrações:", err)
        else:
            print("Gerenciamento de migrações está desativado.")
