from __future__ import annotations

from demo import seed_support_note_embeddings as seeder


class VerificationCursor:
    def __init__(self, *, oracle_text_index: bool):
        self.oracle_text_index = oracle_text_index
        self.executions = []
        self._row = None
        self._rows = []

    def execute(self, sql, parameters=None):
        self.executions.append((sql, parameters))
        normalized = " ".join(sql.split()).upper()
        if "SUM(CASE WHEN EMBEDDING IS NOT NULL" in normalized:
            self._row = (2, 2)
        elif "ORDER BY VECTOR_DISTANCE" in normalized:
            self._rows = [(501, "VPN support note", 0.9)]
        elif "FROM USER_INDEXES" in normalized:
            self._row = (int(self.oracle_text_index),)
        elif "CONTAINS(BODY" in normalized or "UPPER(BODY) LIKE" in normalized:
            self._row = (1,)

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


def test_verify_uses_like_when_oracle_text_index_is_absent(monkeypatch, capsys):
    cursor = VerificationCursor(oracle_text_index=False)
    monkeypatch.setattr(seeder, "embed", lambda _text: [0.1] * seeder.EMBEDDING_DIMENSION)

    seeder.verify(cursor)

    statements = [sql for sql, _ in cursor.executions]
    assert any("UPPER(body) LIKE :vpn" in sql for sql in statements)
    assert not any("CONTAINS(body" in sql for sql in statements)
    assert "text_search_mode=like" in capsys.readouterr().out


def test_verify_uses_contains_when_oracle_text_index_exists(monkeypatch, capsys):
    cursor = VerificationCursor(oracle_text_index=True)
    monkeypatch.setattr(seeder, "embed", lambda _text: [0.1] * seeder.EMBEDDING_DIMENSION)

    seeder.verify(cursor)

    statements = [sql for sql, _ in cursor.executions]
    assert any("CONTAINS(body" in sql for sql in statements)
    assert not any("UPPER(body) LIKE :vpn" in sql for sql in statements)
    assert "text_search_mode=oracle_text" in capsys.readouterr().out


def test_sync_oracle_text_skips_ctx_ddl_without_index():
    cursor = VerificationCursor(oracle_text_index=False)

    seeder.sync_oracle_text(cursor)

    assert not any("CTX_DDL.SYNC_INDEX" in sql for sql, _ in cursor.executions)
