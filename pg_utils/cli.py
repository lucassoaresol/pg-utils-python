import argparse
import json
from pathlib import Path

from .clients_manager import ClientsManager
from .diagram_generator import generate_db_diagram_file
from .migration_create import MigrationCreate
from .migration_manager import MigrationManager

# Diretórios e arquivos de configuração
MIGRATIONS_DIR = Path("migrations")
CONFIG_FILE_PATH = Path("pg-utils.json")
GITIGNORE_PATH = Path(".gitignore")


def handle_migration(db_client: MigrationManager, options):
    """Gerencia as migrações do banco de dados para um cliente específico."""
    try:
        if options.down:
            if options.all:
                print("Revertendo todas as migrações aplicadas.")
                db_client.revert_all_migrations()
            else:
                print("Revertendo a última migração aplicada.")
                db_client.revert_last_migration()
        elif not options.create:
            print("Aplicando todas as migrações pendentes.")
            db_client.apply_all_migrations()
    except Exception as err:
        print(f"Erro ao gerenciar as migrações: {err}")


def init_project(args):
    """Inicializa o projeto criando os diretórios e arquivos necessários."""
    try:
        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
        print(f'Diretório "{MIGRATIONS_DIR}" criado com sucesso.')

        config_content = [
            {
                "id": "development",
                "user": "dev_user",
                "host": "localhost",
                "password": "dev_password",
                "port": 5432,
                "database": "dev_database",
                "migrationsDir": "migrations",
                "manageMigrations": True,
            },
            {
                "id": "production",
                "user": "prod_user",
                "host": "prod-db.example.com",
                "password": "prod_password",
                "port": 5432,
                "database": "prod_database",
                "migrationsDir": "migrations",
                "manageMigrations": False,
            },
        ]

        if not CONFIG_FILE_PATH.exists():
            CONFIG_FILE_PATH.write_text(json.dumps(config_content, indent=2))
            print(f'Arquivo de configuração "{CONFIG_FILE_PATH}" criado com sucesso.')

        if (
            not GITIGNORE_PATH.exists()
            or "pg-utils.json" not in GITIGNORE_PATH.read_text()
        ):
            with open(GITIGNORE_PATH, "a") as gitignore:
                gitignore.write("\npg-utils.json\n")
            print(f'"{CONFIG_FILE_PATH}" adicionado ao .gitignore.')
    except Exception as e:
        print(f"Erro ao inicializar o projeto: {e}")


def add_client(args):
    """Adiciona um novo cliente ao arquivo de configuração."""
    new_client_config = {
        "id": args.id,
        "user": args.user,
        "host": args.host,
        "password": args.password,
        "port": int(args.port),
        "database": args.database,
        "migrationsDir": "migrations",
        "manageMigrations": args.manageMigrations,
    }

    try:
        if CONFIG_FILE_PATH.exists():
            config = json.loads(CONFIG_FILE_PATH.read_text())

            if any(client["id"] == new_client_config["id"] for client in config):
                print(f'Erro: O cliente com ID "{new_client_config["id"]}" já existe.')
                return

            config.append(new_client_config)
            CONFIG_FILE_PATH.write_text(json.dumps(config, indent=2))
            print(f'Cliente "{new_client_config["id"]}" adicionado com sucesso.')
        else:
            print(
                'Erro: O arquivo de configuração "pg-utils.json" não existe. Execute "init" primeiro.'
            )
    except Exception as e:
        print(f"Erro ao adicionar cliente: {e}")


def create_database(args):
    """Cria o banco de dados para um cliente específico ou todos os clientes."""
    try:
        clients_manager = ClientsManager()

        if args.id:
            db_client = clients_manager.get_client_by_id(args.id)
            if db_client:
                db_client.create_and_connect_database()
                print(
                    f'Banco de dados para o cliente "{args.id}" criado/conectado com sucesso.'
                )
            else:
                print(f'Cliente com ID "{args.id}" não encontrado.')
        else:
            for (
                id,
                db_client,
            ) in clients_manager.get_clients_with_manage_migrations().items():
                db_client.create_and_connect_database()
                print(
                    f'Banco de dados para o cliente "{id}" criado/conectado com sucesso.'
                )
    except Exception as e:
        print(f"Erro ao criar banco de dados: {e}")


def migrate(args):
    """Gerencia as migrações do banco de dados."""
    try:
        if args.create:
            migrate = MigrationCreate(MIGRATIONS_DIR)
            migrate.create_migration_file(args.create)
            print(f'Migração "{args.create}" criada com sucesso.')
        else:
            clients_manager = ClientsManager()

            if args.id:
                db_client = clients_manager.get_client_by_id(args.id)
                if not db_client:
                    print(f'Cliente com ID "{args.id}" não encontrado.')
                    return

                migrations = db_client.get_migrations()
                if not migrations:
                    print(
                        "Gerenciamento de migrações não está ativado para este cliente."
                    )
                    return

                handle_migration(migrations, args)
            else:
                for (
                    id,
                    db_client,
                ) in clients_manager.get_clients_with_manage_migrations().items():
                    print(f"Aplicando migrações para o cliente: {id}")
                    migrations = db_client.get_migrations()
                    handle_migration(migrations, args)
    except Exception as e:
        print(f"Erro ao executar comando de migração: {e}")


def generate_diagram(args):
    """Gera um diagrama do banco de dados com base nas migrações."""
    output_file = Path(args.output or "dbdiagram.txt")
    try:
        generate_db_diagram_file(MIGRATIONS_DIR, output_file)
        print(f"Diagrama gerado com sucesso no arquivo: {output_file}")
    except Exception as e:
        print(f"Erro ao gerar o diagrama: {e}")


# Configurando argparse
parser = argparse.ArgumentParser(
    prog="pg-utils", description="Utilitários para gerenciamento de bancos de dados."
)
subparsers = parser.add_subparsers(dest="command")

# Comando init
subparsers.add_parser("init", help="Inicializa o projeto").set_defaults(
    func=init_project
)

# Comando add
parser_add = subparsers.add_parser(
    "add", help="Adiciona um novo cliente ao arquivo de configuração"
)
parser_add.add_argument("-i", "--id", required=True, help="ID do cliente")
parser_add.add_argument("-u", "--user", required=True, help="Usuário do banco de dados")
parser_add.add_argument("-H", "--host", required=True, help="Host do banco de dados")
parser_add.add_argument(
    "-p", "--password", required=True, help="Senha do banco de dados"
)
parser_add.add_argument("-P", "--port", default="5432", help="Porta do banco de dados")
parser_add.add_argument(
    "-d", "--database", required=True, help="Nome do banco de dados"
)
parser_add.add_argument(
    "-m",
    "--manageMigrations",
    action="store_true",
    help="Ativar gerenciamento de migrações",
)
parser_add.set_defaults(func=add_client)

# Comando create
parser_create = subparsers.add_parser("create", help="Cria o banco de dados")
parser_create.add_argument("-i", "--id", help="ID do cliente")
parser_create.set_defaults(func=create_database)

# Comando migrate
parser_migrate = subparsers.add_parser("migrate", help="Gerencia migrações")
parser_migrate.add_argument("-c", "--create", help="Cria uma nova migração")
parser_migrate.add_argument(
    "-d", "--down", action="store_true", help="Reverte a última migração"
)
parser_migrate.add_argument(
    "-a",
    "--all",
    action="store_true",
    help="Aplica a ação (down) para todas as migrações",
)
parser_migrate.add_argument("-i", "--id", help="ID do cliente")
parser_migrate.set_defaults(func=migrate)

# Comando diagram
parser_diagram = subparsers.add_parser(
    "diagram", help="Gera um diagrama do banco de dados"
)
parser_diagram.add_argument(
    "-o", "--output", default="dbdiagram.txt", help="Caminho do arquivo de saída"
)
parser_diagram.set_defaults(func=generate_diagram)


def main():
    """Função principal da CLI para ser chamada pelo entry_point no setup.py."""
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
