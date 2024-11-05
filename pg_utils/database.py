import json
import os
from typing import Any, Dict, List, Optional

import psycopg
from psycopg import sql


class Database:
    def __init__(self, id: str, config_file: str = "pg-utils.json"):
        self.config_file = config_file
        self.config = self.load_config(self.config_file, id)
        self.connection = psycopg.connect(
            dbname=self.config["database"],
            user=self.config["user"],
            password=self.config["password"],
            host=self.config["host"],
            port=self.config["port"],
            autocommit=False,
        )

    @staticmethod
    def load_config(config_file: str, id: str) -> Dict[str, Any]:
        with open(config_file, "r") as file:
            configs = json.load(file)
        for config in configs:
            if config.get("id") == id:
                return config
        raise ValueError(f"Configuração com id '{id}' não encontrada.")

    def execute_query_all(
        self, query: str, params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results

    def execute_query_field(
        self, query: str, params: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            result = cursor.fetchone()
            if result:
                return {columns[i]: value for i, value in enumerate(result)}
            return None

    def insert_into_table(
        self, table_name: str, data_dict: Dict[str, Any], returning: str = "id"
    ) -> Any:
        columns = data_dict.keys()
        values = [data_dict[col] for col in columns]

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(values)),
            sql.Identifier(returning),
        )

        with self.connection.cursor() as cursor:
            cursor.execute(insert_query, values)
            result = cursor.fetchone()
            self.connection.commit()
            return result[0] if result else None

    def update_into_table(self, table_name: str, data_dict: Dict[str, Any]) -> None:
        query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(k))
                for k in data_dict.keys()
                if k != "id"
            ),
        )
        with self.connection.cursor() as cursor:
            cursor.execute(query, list(data_dict.values())[1:] + [data_dict["id"]])
            self.connection.commit()

    def delete_into_table(self, table: str, field: str, value: Any) -> None:
        query = sql.SQL("DELETE FROM {} WHERE {} = %s").format(
            sql.Identifier(table), sql.Identifier(field)
        )
        with self.connection.cursor() as cursor:
            cursor.execute(query, (value,))
            self.connection.commit()

    def search_all(
        self, table: str, fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if fields:
            query = sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(", ").join(sql.Identifier(f) for f in fields),
                sql.Identifier(table),
            )
        else:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
        return self.execute_query_all(query)

    def search_by_field(
        self, table: str, field: str, value: Any, fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if fields:
            query = sql.SQL("SELECT {} FROM {} WHERE {} = %s").format(
                sql.SQL(", ").join(sql.Identifier(f) for f in fields),
                sql.Identifier(table),
                sql.Identifier(field),
            )
        else:
            query = sql.SQL("SELECT * FROM {} WHERE {} = %s").format(
                sql.Identifier(table),
                sql.Identifier(field),
            )
        return self.execute_query_all(query, [value])

    def close(self):
        self.connection.close()
