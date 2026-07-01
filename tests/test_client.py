from __future__ import annotations

import datetime as dt
import decimal

from oracle_ai_database.client import OracleDatabaseClient
from oracle_ai_database.credentials import OracleCredentials


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

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


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
