from __future__ import annotations

import array
import json
import os
import urllib.request
from typing import Any

import oracledb


EMBEDDING_DIMENSION = 768
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

ADDITIONAL_TICKETS = [
    {
        "ticket_id": 1005,
        "customer_id": 1,
        "title": "Remote access authentication state remains stale",
        "severity": "P2",
        "status": "IN_PROGRESS",
        "product": "Identity",
        "created_at": "2025-02-12",
        "summary": (
            "Acme Bank users remain locked out of remote access after changing directory credentials because "
            "cached authentication state has not refreshed."
        ),
    },
    {
        "ticket_id": 1006,
        "customer_id": 3,
        "title": "Oracle listener unavailable after network maintenance",
        "severity": "P1",
        "status": "OPEN",
        "product": "Database",
        "created_at": "2025-02-13",
        "summary": (
            "Northwind Health reports ORA-12541 and failed database connections following network maintenance."
        ),
    },
]

ADDITIONAL_NOTES = [
    {
        "id": 504,
        "ticket_id": 1005,
        "customer_name": "Acme Bank",
        "title": "Credential cache recovery after directory change",
        "body": (
            "Remote access sessions can fail after directory credentials change while cached authentication state "
            "remains stale. Clear cached credentials, confirm directory replication, validate MFA enrollment, and "
            "retry the remote access client after the synchronization window."
        ),
        "tags": "remote-access,credential-cache,directory-sync,mfa,acme-bank",
        "created_at": "2025-02-12",
    },
    {
        "id": 505,
        "ticket_id": 1006,
        "customer_name": "Northwind Health",
        "title": "ORA-12541 listener connectivity runbook",
        "body": (
            "ORA-12541 means that a connection reached no Oracle listener at the requested host and port. Verify the "
            "listener service, network route, wallet service alias, DNS resolution, and firewall rules before retrying."
        ),
        "tags": "ora-12541,listener,network,wallet,database",
        "created_at": "2025-02-13",
    },
    {
        "id": 506,
        "ticket_id": 1006,
        "customer_name": "Northwind Health",
        "title": "Connection pool recovery after network interruption",
        "body": (
            "Long-running application workers may retain stale pooled database sessions after a network interruption. "
            "Validate connections when acquired, discard DPY-4011 closed sessions, bound the pool size, and retry the "
            "failed indexing operation with a healthy connection."
        ),
        "tags": "connection-pool,dpy-4011,retry,indexing,database",
        "created_at": "2025-02-13",
    },
]


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def connect_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "user": required_env("ORACLE_USER"),
        "password": required_env("ORACLE_PASSWORD"),
        "dsn": required_env("ORACLE_DSN"),
    }
    for env_name, argument_name in (
        ("ORACLE_CONFIG_DIR", "config_dir"),
        ("ORACLE_WALLET_LOCATION", "wallet_location"),
        ("ORACLE_WALLET_PASSWORD", "wallet_password"),
    ):
        value = optional_env(env_name)
        if value:
            kwargs[argument_name] = value
    return kwargs


def embed(text: str) -> list[float]:
    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embed",
        data=json.dumps({"model": OLLAMA_EMBED_MODEL, "input": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=120) as response:
        payload = json.load(response)
    embeddings = payload.get("embeddings") or []
    if not embeddings or not isinstance(embeddings[0], list):
        raise RuntimeError("Ollama did not return an embedding")
    vector = [float(value) for value in embeddings[0]]
    if len(vector) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"Expected {EMBEDDING_DIMENSION} embedding dimensions from {OLLAMA_EMBED_MODEL}, got {len(vector)}"
        )
    return vector


def ensure_embedding_column(cursor: Any) -> None:
    cursor.execute(
        "SELECT data_type FROM user_tab_columns WHERE table_name = 'DEMO_SUPPORT_NOTES' AND column_name = 'EMBEDDING'"
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(f"ALTER TABLE DEMO_SUPPORT_NOTES ADD (EMBEDDING VECTOR({EMBEDDING_DIMENSION}, FLOAT32))")
    elif not str(row[0]).upper().startswith("VECTOR"):
        raise RuntimeError("DEMO_SUPPORT_NOTES.EMBEDDING exists but is not a VECTOR column")


def upsert_tickets(cursor: Any) -> None:
    sql = """
        MERGE INTO DEMO_SUPPORT_TICKETS target
        USING (SELECT :ticket_id AS ticket_id FROM dual) source
        ON (target.ticket_id = source.ticket_id)
        WHEN MATCHED THEN UPDATE SET
            target.customer_id = :customer_id,
            target.title = :title,
            target.severity = :severity,
            target.status = :status,
            target.product = :product,
            target.created_at = TO_DATE(:created_at, 'YYYY-MM-DD'),
            target.summary = :summary
        WHEN NOT MATCHED THEN INSERT (
            ticket_id, customer_id, title, severity, status, product, created_at, summary
        ) VALUES (
            :ticket_id, :customer_id, :title, :severity, :status, :product,
            TO_DATE(:created_at, 'YYYY-MM-DD'), :summary
        )
    """
    cursor.executemany(sql, ADDITIONAL_TICKETS)


def upsert_notes(cursor: Any) -> None:
    sql = """
        MERGE INTO DEMO_SUPPORT_NOTES target
        USING (SELECT :id AS id FROM dual) source
        ON (target.id = source.id)
        WHEN MATCHED THEN UPDATE SET
            target.ticket_id = :ticket_id,
            target.customer_name = :customer_name,
            target.title = :title,
            target.body = :body,
            target.tags = :tags,
            target.created_at = TO_DATE(:created_at, 'YYYY-MM-DD')
        WHEN NOT MATCHED THEN INSERT (
            id, ticket_id, customer_name, title, body, tags, created_at
        ) VALUES (
            :id, :ticket_id, :customer_name, :title, :body, :tags,
            TO_DATE(:created_at, 'YYYY-MM-DD')
        )
    """
    cursor.executemany(sql, ADDITIONAL_NOTES)


def update_embeddings(cursor: Any) -> int:
    cursor.execute("SELECT id, body FROM DEMO_SUPPORT_NOTES ORDER BY id")
    notes = [(int(note_id), body.read() if hasattr(body, "read") else str(body)) for note_id, body in cursor]
    for note_id, body in notes:
        cursor.execute(
            "UPDATE DEMO_SUPPORT_NOTES SET embedding = :embedding WHERE id = :id",
            {"embedding": array.array("f", embed(body)), "id": note_id},
        )
    return len(notes)


def sync_oracle_text(cursor: Any) -> None:
    cursor.execute("SELECT COUNT(*) FROM user_indexes WHERE index_name = 'DEMO_SUPPORT_NOTES_CTX_IDX'")
    if cursor.fetchone()[0]:
        cursor.execute("BEGIN CTX_DDL.SYNC_INDEX('DEMO_SUPPORT_NOTES_CTX_IDX'); END;")


def verify(cursor: Any) -> None:
    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) FROM DEMO_SUPPORT_NOTES")
    total, vectorized = cursor.fetchone()
    if total != vectorized:
        raise RuntimeError(f"Expected all support notes to be vectorized, got {vectorized}/{total}")

    query_vector = array.array(
        "f",
        embed("Acme Bank users cannot connect remotely after changing their password and credentials"),
    )
    cursor.execute(
        """
        SELECT id, title,
               1 - VECTOR_DISTANCE(embedding, :query_vector, COSINE) AS vector_score
        FROM DEMO_SUPPORT_NOTES
        WHERE embedding IS NOT NULL
        ORDER BY VECTOR_DISTANCE(embedding, :query_vector, COSINE)
        FETCH FIRST 3 ROWS ONLY
        """,
        {"query_vector": query_vector},
    )
    matches = cursor.fetchall()
    if not matches:
        raise RuntimeError("Vector verification returned no support notes")

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM DEMO_SUPPORT_NOTES
        WHERE CONTAINS(body, 'VPN ACCUM password ACCUM synchronization', 1) > 0
        """
    )
    text_matches = cursor.fetchone()[0]
    if not text_matches:
        raise RuntimeError("Oracle Text verification returned no support notes")

    print(f"support_notes={total}")
    print(f"vectorized_notes={vectorized}")
    print(f"oracle_text_matches={text_matches}")
    print("top_vector_matches=" + ",".join(f"{row[0]}:{float(row[2]):.4f}" for row in matches))


def main() -> None:
    with oracledb.connect(**connect_kwargs()) as connection:
        with connection.cursor() as cursor:
            ensure_embedding_column(cursor)
            upsert_tickets(cursor)
            upsert_notes(cursor)
            connection.commit()
            updated = update_embeddings(cursor)
            connection.commit()
            sync_oracle_text(cursor)
            verify(cursor)
            print(f"updated_embeddings={updated}")


if __name__ == "__main__":
    main()
