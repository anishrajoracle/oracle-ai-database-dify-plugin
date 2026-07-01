from __future__ import annotations

import array
import datetime as dt
import decimal
from dataclasses import dataclass
from typing import Any, Callable

from oracle_ai_database.credentials import OracleCredentials
from oracle_ai_database.sql_safety import SafeSql, validate_read_only_sql


ConnectFunc = Callable[..., Any]


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
        }


def _default_connect(**kwargs: Any) -> Any:
    import oracledb

    return oracledb.connect(**kwargs)


def to_vector(values: list[float]) -> array.array:
    return array.array("f", values)


def serialize_value(value: Any) -> Any:
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, decimal.Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


class OracleDatabaseClient:
    def __init__(self, credentials: OracleCredentials, connect: ConnectFunc | None = None):
        self.credentials = credentials
        self._connect = connect or _default_connect

    @classmethod
    def from_credentials(cls, credentials: dict[str, Any], connect: ConnectFunc | None = None) -> OracleDatabaseClient:
        return cls(OracleCredentials.from_mapping(credentials), connect=connect)

    def _open_connection(self) -> Any:
        return self._connect(**self.credentials.connect_kwargs())

    def ping(self) -> None:
        connection = self._open_connection()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1 FROM dual")
                cursor.fetchone()
            finally:
                close = getattr(cursor, "close", None)
                if close:
                    close()
        finally:
            close = getattr(connection, "close", None)
            if close:
                close()

    def execute_read_only(
        self,
        sql: str | SafeSql,
        *,
        binds: dict[str, Any] | None = None,
        max_rows: int,
    ) -> QueryResult:
        safe_sql = sql if isinstance(sql, SafeSql) else validate_read_only_sql(sql)
        connection = self._open_connection()
        try:
            cursor = connection.cursor()
            try:
                cursor.arraysize = max_rows
                cursor.execute(safe_sql.sql, binds or {})
                rows = cursor.fetchmany(max_rows + 1)
                truncated = len(rows) > max_rows
                visible_rows = rows[:max_rows]
                columns = [description[0] for description in (cursor.description or [])]
                row_dicts = [
                    {columns[index]: serialize_value(value) for index, value in enumerate(row)}
                    for row in visible_rows
                ]
                return QueryResult(
                    columns=columns,
                    rows=row_dicts,
                    row_count=len(row_dicts),
                    truncated=truncated,
                )
            finally:
                close = getattr(cursor, "close", None)
                if close:
                    close()
        finally:
            close = getattr(connection, "close", None)
            if close:
                close()

    def execute_vector_search(
        self,
        sql: str | SafeSql,
        *,
        query_vector: list[float],
        max_rows: int,
    ) -> QueryResult:
        safe_sql = sql if isinstance(sql, SafeSql) else validate_read_only_sql(sql)
        return self.execute_read_only(
            safe_sql,
            binds={"query_vector": to_vector(query_vector)},
            max_rows=max_rows,
        )

    def execute_hybrid_search(
        self,
        sql: str | SafeSql,
        *,
        query: str,
        query_vector: list[float],
        vector_weight: float,
        text_weight: float,
        max_rows: int,
    ) -> QueryResult:
        safe_sql = sql if isinstance(sql, SafeSql) else validate_read_only_sql(sql)
        return self.execute_read_only(
            safe_sql,
            binds={
                "query": query,
                "query_vector": to_vector(query_vector),
                "vector_weight": vector_weight,
                "text_weight": text_weight,
            },
            max_rows=max_rows,
        )

    def select_ai(self, *, prompt: str, profile_name: str, action: str) -> str:
        sql = (
            "SELECT DBMS_CLOUD_AI.GENERATE("
            "prompt => :prompt, profile_name => :profile_name, action => :action"
            ") AS response FROM dual"
        )
        connection = self._open_connection()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    sql,
                    {
                        "prompt": prompt,
                        "profile_name": profile_name,
                        "action": action,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    return ""
                return str(serialize_value(row[0]) or "")
            finally:
                close = getattr(cursor, "close", None)
                if close:
                    close()
        finally:
            close = getattr(connection, "close", None)
            if close:
                close()
