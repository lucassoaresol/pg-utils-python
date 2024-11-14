import json
from typing import Any, Dict, List, Literal, Optional, Tuple

import psycopg
from psycopg import sql

from .database_types import JoinParams, WhereClause, WhereCondition


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
                if "value" in condition and "mode" in condition:
                    if condition["mode"] == "not":
                        if condition["value"] is None:
                            conditions_array.append(f"{column} IS NOT NULL")
                        else:
                            conditions_array.append(f"{column} != %s")
                            where_values.append(condition["value"])
                    else:
                        conditions_array.append(f"{column} = %s")
                        where_values.append(condition["value"])
                elif any(op in condition for op in ("lt", "lte", "gt", "gte")):
                    if "lt" in condition:
                        conditions_array.append(f"{column} < %s")
                        where_values.append(condition["lt"])
                    if "lte" in condition:
                        conditions_array.append(f"{column} <= %s")
                        where_values.append(condition["lte"])
                    if "gt" in condition:
                        conditions_array.append(f"{column} > %s")
                        where_values.append(condition["gt"])
                    if "gte" in condition:
                        conditions_array.append(f"{column} >= %s")
                        where_values.append(condition["gte"])
            else:
                conditions_array.append(f"{column} = %s")
                where_values.append(condition)

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
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results

    def insert_into_table(
        self,
        table: str,
        data_dict: Dict[str, Any],
        select: Optional[Dict[str, bool]] = None,
    ) -> Any:
        columns = [col for col in data_dict.keys() if data_dict[col] is not None]
        values = [data_dict[col] for col in columns]

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

    def update_into_table(
        self,
        table: str,
        data_dict: Dict[str, Any],
        where: Optional[WhereClause] = None,
    ) -> None:
        columns = [col for col in data_dict.keys() if data_dict[col] is not None]
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
                    if "." not in key:
                        selected_fields.append(f"{main_table_alias}.{key}")
                    else:
                        sl_split = key.split(".")
                        sl_alias = sl_split[0]
                        column_name = sl_split[-1]
                        if sl_alias != main_table_alias:
                            selected_fields.append(f"{key} AS {sl_alias}_{column_name}")
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

                if not select:
                    join_columns = self.find_many(
                        "information_schema.columns",
                        "i",
                        where={"table_name": join.table},
                        select={"column_name": True},
                    )
                    selected_fields.extend(
                        f"{join_alias}.{column['column_name']} AS {join_alias}_{column['column_name']}"
                        for column in join_columns
                    )

                join_conditions = " AND ".join(
                    f"{main_table_alias}.{key} = {join_alias}.{value}"
                    for key, value in join["on"].items()
                )

                query_aux += f" {join_type} JOIN {join['table']} AS {join_alias} ON {join_conditions}"

        where_clause, where_values = self.build_where_clause(
            where, main_table_alias=main_table_alias
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

        query = (
            f"SELECT {', '.join(selected_fields)} FROM {table} AS {main_table_alias} "
            + query_aux
            + f" {where_clause} {order_clause} {limit_clause};"
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

    def close(self):
        self.connection.close()
