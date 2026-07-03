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
    serialize_value,
    to_vector,
)
from oracle_ai_database.credentials import (
    DEFAULT_TCP_CONNECT_TIMEOUT_SECONDS,
    OracleCredentials,
    redact_connection_values,
)


class FakeCursor:
    def __init__(self, rows=None, one=None):
        self.rows = rows or []
        self.one = one
        self.description = [("ID",), ("CREATED_AT",), ("AMOUNT",)]
        self.executed = []
        self.arraysize = None
        self.closed = False

    def execute(self, sql, binds=None):
        self.executed.append((sql, binds or {}))

    def fetchmany(self, size):
        return self.rows[:size]

    def fetchone(self):
        return self.one

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.closed = False
        self.call_timeout = None

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


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
