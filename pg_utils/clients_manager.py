import json
import os
from typing import Dict, Optional
from .pg_utils import PgUtils


class ClientsManager:
    _instance: Optional["ClientsManager"] = None
    _clients_map: Dict[str, PgUtils] = {}
    _config_file_path: str = os.path.abspath("pg-utils.json")

    def __new__(cls) -> "ClientsManager":
        if cls._instance is None:
            cls._instance = super(ClientsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Initialize instance only once
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.load_clients_config()

    def load_clients_config(self) -> None:
        try:
            with open(self._config_file_path, "r", encoding="utf-8") as config_file:
                config = json.load(config_file)
                for client in config:
                    pg_utils_instance = PgUtils(
                        client["user"],
                        client["host"],
                        client["password"],
                        client["port"],
                        client["database"],
                        client["migrationsDir"],
                        client["manageMigrations"],
                    )
                    self._clients_map[client["id"]] = pg_utils_instance
        except Exception as e:
            print(f"Error loading client configurations: {str(e)}")
            raise e

    def get_client_by_id(self, client_id: str) -> Optional[PgUtils]:
        return self._clients_map.get(client_id)

    def get_all_clients(self) -> Dict[str, PgUtils]:
        return self._clients_map

    def get_clients_with_manage_migrations(self) -> Dict[str, PgUtils]:
        clients_with_migrations = {}
        for client_id, client in self._clients_map.items():
            if client.get_manage_migrations():
                clients_with_migrations[client_id] = client
        return clients_with_migrations
