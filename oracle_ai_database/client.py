from __future__ import annotations

import array
import datetime as dt
import decimal
import math
from dataclasses import dataclass
from typing import Any, Callable

from oracle_ai_database.credentials import OracleCredentials
from oracle_ai_database.sql_safety import (
    MAX_WRITE_ROWS,
    SafeSql,
    parse_write_bind_parameters,
    validate_read_only_sql,
    validate_write_only_sql,
)


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


@dataclass(frozen=True)
class WriteResult:
    operation: str
    target_table: str
    affected_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "operation": self.operation,
            "target_table": self.target_table,
            "affected_rows": self.affected_rows,
            "committed": True,
        }


class WriteLimitExceededError(RuntimeError):
    """Raised when Oracle cannot prove a write stayed within its configured row limit."""


class WriteCommitOutcomeUnknownError(RuntimeError):
    """Raised when Oracle does not confirm whether a write commit completed."""


def _default_connect(**kwargs: Any) -> Any:
    import oracledb

    return oracledb.connect(**kwargs)


def to_vector(values: list[float]) -> array.array:
    vector = array.array("f", values)
    if any(not math.isfinite(value) for value in vector):
        raise ValueError("query_vector values must fit in the finite FLOAT32 range.")
    return vector


def _read_lob(value: Any) -> Any:
    try:
        content = value.read(1, MAX_LOB_UNITS + 1)
    except TypeError:
        content = value.read(MAX_LOB_UNITS + 1)
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


def _close_after_write(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        # A confirmed commit must not look failed and trigger an unsafe retry.
        pass


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

    def execute_write_only(
        self,
        sql: str,
        *,
        binds: dict[str, Any] | None = None,
        allowed_tables: set[str] | frozenset[str],
        allow_delete: bool,
        max_affected_rows: int,
    ) -> WriteResult:
        if (
            not isinstance(max_affected_rows, int)
            or isinstance(max_affected_rows, bool)
            or max_affected_rows < 1
            or max_affected_rows > MAX_WRITE_ROWS
        ):
            raise ValueError(f"max_affected_rows must be between 1 and {MAX_WRITE_ROWS}.")
        safe_sql = validate_write_only_sql(
            sql,
            allowed_tables=allowed_tables,
            allow_delete=allow_delete,
        )
        safe_binds = parse_write_bind_parameters(safe_sql.sql, binds)
        connection = self._open_connection()
        try:
            connection.autocommit = False
            cursor = connection.cursor()
            try:
                try:
                    cursor.execute(safe_sql.sql, safe_binds)
                    affected_rows = cursor.rowcount
                    if not isinstance(affected_rows, int) or isinstance(affected_rows, bool) or affected_rows < 0:
                        raise WriteLimitExceededError(
                            "Oracle did not report a valid affected row count; the transaction was rolled back."
                        )
                    if affected_rows > max_affected_rows:
                        raise WriteLimitExceededError(
                            f"Write affected {affected_rows} rows, exceeding the configured limit of "
                            f"{max_affected_rows}; the transaction was rolled back."
                        )
                except Exception:
                    connection.rollback()
                    raise
                try:
                    connection.commit()
                except Exception:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    raise WriteCommitOutcomeUnknownError(
                        "Oracle commit outcome is unknown. Do not retry this write automatically."
                    ) from None
                return WriteResult(
                    operation=safe_sql.operation,
                    target_table=safe_sql.target_table,
                    affected_rows=affected_rows,
                )
            finally:
                _close_after_write(cursor)
        finally:
            _close_after_write(connection)

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
