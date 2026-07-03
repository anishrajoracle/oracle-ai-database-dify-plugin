from __future__ import annotations

import datetime as dt
import decimal
from array import array

import pytest

from oracle_ai_database.client import (
    DEFAULT_CALL_TIMEOUT_MS,
    MAX_LOB_UNITS,
    TRUNCATED_SUFFIX,
    OracleDatabaseClient,
    WriteLimitExceededError,
    WriteCommitOutcomeUnknownError,
    serialize_value,
    to_vector,
)
from oracle_ai_database.credentials import (
    DEFAULT_TCP_CONNECT_TIMEOUT_SECONDS,
    OracleCredentials,
    redact_connection_values,
)


class FakeCursor:
    def __init__(self, rows=None, one=None, rowcount=0, execute_error=None, close_error=None):
        self.rows = rows or []
        self.one = one
        self.description = [("ID",), ("CREATED_AT",), ("AMOUNT",)]
        self.executed = []
        self.arraysize = None
        self.closed = False
        self.rowcount = rowcount
        self.execute_error = execute_error
        self.close_error = close_error

    def execute(self, sql, binds=None):
        self.executed.append((sql, binds or {}))
        if self.execute_error is not None:
            raise self.execute_error

    def fetchmany(self, size):
        return self.rows[:size]

    def fetchone(self):
        return self.one

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class FakeConnection:
    def __init__(self, cursor, commit_error=None, close_error=None):
        self.cursor_obj = cursor
        self.closed = False
        self.call_timeout = None
        self.committed = False
        self.rolled_back = False
        self.autocommit = None
        self.commit_error = commit_error
        self.close_error = close_error

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error

    def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_to_vector_rejects_values_that_overflow_float32():
    assert to_vector([0.25, 0.5]).typecode == "f"

    with pytest.raises(ValueError, match="finite FLOAT32 range"):
        to_vector([3.4028236e38])


def test_credentials_build_dsn_and_wallet_kwargs():
    credentials = OracleCredentials.from_mapping(
        {
            "user": "app",
            "password": "secret",
            "host": "db.example.com",
            "port": "1522",
            "service_name": "FREEPDB1",
            "wallet_location": "/wallet",
        }
    )

    assert credentials.dsn == "db.example.com:1522/FREEPDB1"
    assert credentials.connect_kwargs()["wallet_location"] == "/wallet"
    assert credentials.connect_kwargs()["tcp_connect_timeout"] == DEFAULT_TCP_CONNECT_TIMEOUT_SECONDS


def test_error_message_redacts_configured_connection_values():
    message = redact_connection_values(
        "Login failed for app_user at db.example.com:1521/FREEPDB1 with change-me",
        {
            "user": "app_user",
            "password": "change-me",
            "dsn": "db.example.com:1521/FREEPDB1",
        },
    )

    assert message == "Login failed for [REDACTED] at [REDACTED] with [REDACTED]"

    short_secret_message = redact_connection_values("Login failed with x", {"password": "x"})
    assert short_secret_message == "Oracle database operation failed. Sensitive connection details were redacted."


class FakeLob:
    def __init__(self, content):
        self.content = content

    def read(self, offset, amount):
        assert offset == 1
        assert amount == MAX_LOB_UNITS + 1
        return self.content[:amount]


class FakeOneArgumentLob:
    def __init__(self, content):
        self.content = content

    def read(self, amount):
        assert amount == MAX_LOB_UNITS + 1
        return self.content[:amount]


def test_serialize_value_handles_vectors_and_bounds_lobs():
    assert serialize_value(array("f", [0.25, 0.5])) == [0.25, 0.5]
    assert serialize_value(FakeLob("x" * (MAX_LOB_UNITS + 1))) == "x" * MAX_LOB_UNITS + TRUNCATED_SUFFIX
    assert serialize_value(FakeOneArgumentLob("x" * (MAX_LOB_UNITS + 1))) == ("x" * MAX_LOB_UNITS + TRUNCATED_SUFFIX)
    assert serialize_value(FakeLob(b"x" * (MAX_LOB_UNITS + 1))) == ((b"x" * MAX_LOB_UNITS).hex() + TRUNCATED_SUFFIX)


def test_execute_read_only_uses_binds_and_serializes_rows():
    cursor = FakeCursor(
        rows=[
            (1, dt.date(2026, 6, 18), decimal.Decimal("10.50")),
            (2, dt.date(2026, 6, 19), decimal.Decimal("11")),
        ]
    )
    connection = FakeConnection(cursor)
    client = OracleDatabaseClient.from_credentials(
        {"user": "app", "password": "secret", "dsn": "db/pdb"},
        connect=lambda **_kwargs: connection,
    )

    result = client.execute_read_only(
        "select id, created_at, amount from invoices where id = :invoice_id",
        binds={"invoice_id": 1},
        max_rows=1,
    )

    assert cursor.executed == [
        (
            "select id, created_at, amount from invoices where id = :invoice_id",
            {"invoice_id": 1},
        )
    ]
    assert result.to_dict() == {
        "status": "success",
        "columns": ["ID", "CREATED_AT", "AMOUNT"],
        "rows": [{"ID": 1, "CREATED_AT": "2026-06-18", "AMOUNT": 10.5}],
        "row_count": 1,
        "truncated": True,
    }
    assert cursor.closed
    assert connection.closed
    assert connection.call_timeout == DEFAULT_CALL_TIMEOUT_MS


def test_execute_write_only_commits_bounded_dml_and_returns_no_rows():
    cursor = FakeCursor(rowcount=1)
    connection = FakeConnection(cursor)
    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=lambda **_kwargs: connection,
    )

    result = client.execute_write_only(
        "update tickets set status = :status where id = :id",
        binds={"status": "CLOSED", "id": 42},
        allowed_tables={"TICKETS"},
        allow_delete=False,
        max_affected_rows=1,
    )

    assert result.to_dict() == {
        "status": "success",
        "operation": "UPDATE",
        "target_table": "TICKETS",
        "affected_rows": 1,
        "committed": True,
    }
    assert cursor.executed == [
        (
            "update tickets set status = :status where id = :id",
            {"status": "CLOSED", "id": 42},
        )
    ]
    assert connection.autocommit is False
    assert connection.committed
    assert not connection.rolled_back
    assert cursor.closed
    assert connection.closed


@pytest.mark.parametrize("rowcount", [2, -1, None])
def test_execute_write_only_rolls_back_when_affected_rows_are_over_or_unknown(rowcount):
    cursor = FakeCursor(rowcount=rowcount)
    connection = FakeConnection(cursor)
    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=lambda **_kwargs: connection,
    )

    with pytest.raises(WriteLimitExceededError):
        client.execute_write_only(
            "update tickets set status = :status where id = :id",
            binds={"status": "CLOSED", "id": 42},
            allowed_tables={"TICKETS"},
            allow_delete=False,
            max_affected_rows=1,
        )

    assert connection.rolled_back
    assert not connection.committed
    assert cursor.closed
    assert connection.closed


def test_execute_write_only_rolls_back_when_oracle_execution_fails():
    cursor = FakeCursor(execute_error=RuntimeError("write failed"))
    connection = FakeConnection(cursor)
    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=lambda **_kwargs: connection,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        client.execute_write_only(
            "insert into tickets (id) values (:id)",
            binds={"id": 42},
            allowed_tables={"TICKETS"},
            allow_delete=False,
            max_affected_rows=1,
        )

    assert connection.rolled_back
    assert not connection.committed
    assert cursor.closed
    assert connection.closed


def test_execute_write_only_rolls_back_when_commit_fails():
    cursor = FakeCursor(rowcount=1)
    connection = FakeConnection(cursor, commit_error=RuntimeError("commit failed"))
    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=lambda **_kwargs: connection,
    )

    with pytest.raises(WriteCommitOutcomeUnknownError, match="commit outcome is unknown"):
        client.execute_write_only(
            "insert into tickets (id) values (:id)",
            binds={"id": 42},
            allowed_tables={"TICKETS"},
            allow_delete=False,
            max_affected_rows=1,
        )

    assert connection.rolled_back
    assert not connection.committed
    assert cursor.closed
    assert connection.closed


def test_execute_write_only_validates_before_opening_connection():
    connection_attempted = False

    def connect(**_kwargs):
        nonlocal connection_attempted
        connection_attempted = True
        raise AssertionError("connection should not be opened")

    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=connect,
    )

    with pytest.raises(ValueError, match="Only INSERT, UPDATE, or DELETE"):
        client.execute_write_only(
            "select * from tickets",
            binds={},
            allowed_tables={"TICKETS"},
            allow_delete=False,
            max_affected_rows=1,
        )

    assert not connection_attempted


@pytest.mark.parametrize("max_affected_rows", [0, 101, True])
def test_execute_write_only_enforces_hard_row_limit_before_connecting(max_affected_rows):
    connection_attempted = False

    def connect(**_kwargs):
        nonlocal connection_attempted
        connection_attempted = True
        raise AssertionError("connection should not be opened")

    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=connect,
    )

    with pytest.raises(ValueError, match="max_affected_rows must be between 1 and 100"):
        client.execute_write_only(
            "insert into tickets (id) values (:id)",
            binds={"id": 42},
            allowed_tables={"TICKETS"},
            allow_delete=False,
            max_affected_rows=max_affected_rows,
        )

    assert not connection_attempted


@pytest.mark.parametrize("failing_resource", ["cursor", "connection"])
def test_execute_write_only_preserves_confirmed_commit_when_cleanup_fails(failing_resource):
    cursor = FakeCursor(
        rowcount=1,
        close_error=RuntimeError("cursor close failed") if failing_resource == "cursor" else None,
    )
    connection = FakeConnection(
        cursor,
        close_error=RuntimeError("connection close failed") if failing_resource == "connection" else None,
    )
    client = OracleDatabaseClient.from_credentials(
        {"user": "writer", "password": "secret", "dsn": "db/pdb"},
        connect=lambda **_kwargs: connection,
    )

    result = client.execute_write_only(
        "insert into tickets (id) values (:id)",
        binds={"id": 42},
        allowed_tables={"TICKETS"},
        allow_delete=False,
        max_affected_rows=1,
    )

    assert result.to_dict()["committed"] is True
    assert connection.committed
    assert cursor.closed
    assert connection.closed
