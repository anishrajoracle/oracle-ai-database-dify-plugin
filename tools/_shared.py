from __future__ import annotations

from typing import Any

from oracle_ai_database.client import OracleDatabaseClient
from oracle_ai_database.credentials import redact_connection_values


def credentials_from_runtime(tool: Any) -> dict[str, Any]:
    runtime = getattr(tool, "runtime", None)
    credentials = getattr(runtime, "credentials", None) if runtime is not None else None
    return dict(credentials or {})


def client_from_runtime(tool: Any) -> OracleDatabaseClient:
    return OracleDatabaseClient.from_credentials(credentials_from_runtime(tool))


def error_payload(exc: Exception, *, tool: Any | None = None) -> dict[str, Any]:
    credentials = credentials_from_runtime(tool) if tool is not None else {}
    return {
        "status": "error",
        "message": redact_connection_values(exc, credentials),
    }


def require_text(value: Any, *, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required.")
    return text
