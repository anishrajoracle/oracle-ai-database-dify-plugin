from __future__ import annotations

import re
from typing import Any

from oracle_ai_database.client import OracleDatabaseClient
from oracle_ai_database.sql_safety import SqlSafetyError, validate_identifier


SELECT_AI_ACTIONS = {"chat", "narrate", "showsql", "explainsql"}
SQL_BLOCK = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
SQL_START = re.compile(r"\b(SELECT|WITH)\b", re.IGNORECASE)


def credentials_from_runtime(tool: Any) -> dict[str, Any]:
    runtime = getattr(tool, "runtime", None)
    credentials = getattr(runtime, "credentials", None) if runtime is not None else None
    return dict(credentials or {})


def client_from_runtime(tool: Any) -> OracleDatabaseClient:
    return OracleDatabaseClient.from_credentials(credentials_from_runtime(tool))


def error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "status": "error",
        "message": str(exc),
    }


def require_text(value: Any, *, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required.")
    return text


def validate_select_ai_action(action: Any) -> str:
    normalized = str(action or "chat").strip().lower()
    if normalized not in SELECT_AI_ACTIONS:
        raise ValueError(f"action must be one of: {', '.join(sorted(SELECT_AI_ACTIONS))}.")
    return normalized


def validate_select_ai_profile(profile_name: Any) -> str:
    return validate_identifier(require_text(profile_name, name="profile_name"), label="Select AI profile name")


def extract_sql_from_select_ai_response(response: str) -> str:
    text = str(response or "").strip()
    block = SQL_BLOCK.search(text)
    if block:
        text = block.group(1).strip()
    start = SQL_START.search(text)
    if not start:
        raise SqlSafetyError("Select AI did not return a SELECT or WITH statement.")
    return text[start.start() :].strip()

