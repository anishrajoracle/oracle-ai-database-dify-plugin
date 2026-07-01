from __future__ import annotations

import array
import datetime as dt
import decimal
from dataclasses import dataclass
from typing import Any, Callable

from oracle_ai_database.credentials import OracleCredentials
from oracle_ai_database.sql_safety import SafeSql, validate_read_only_sql


ConnectFunc = Callable[..., Any]
DEFAULT_CALL_TIMEOUT_MS = 110_000
MAX_LOB_UNITS = 16_384
TRUNCATED_SUFFIX = "...[truncated]"


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


def _read_lob(value: Any) -> Any:
    try:
        content = value.read(1, MAX_LOB_UNITS + 1)
    except TypeError:
        content = value.read()
    if isinstance(content, str) and len(content) > MAX_LOB_UNITS:
        return content[:MAX_LOB_UNITS] + TRUNCATED_SUFFIX
    if isinstance(content, bytes) and len(content) > MAX_LOB_UNITS:
        return content[:MAX_LOB_UNITS].hex() + TRUNCATED_SUFFIX
    return content


def serialize_value(value: Any) -> Any:
    if hasattr(value, "read"):
        value = _read_lob(value)
    if isinstance(value, array.array):
        return value.tolist()
    if isinstance(value, decimal.Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, bytes):
        if len(value) > MAX_LOB_UNITS:
            return value[:MAX_LOB_UNITS].hex() + TRUNCATED_SUFFIX
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
        connection = self._connect(**self.credentials.connect_kwargs())
        connection.call_timeout = DEFAULT_CALL_TIMEOUT_MS
        return connection

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
                    {columns[index]: serialize_value(value) for index, value in enumerate(row)} for row in visible_rows
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
