from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


MAX_READ_ROWS = 1000
MAX_SEARCH_ROWS = 100
ORACLE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
SQL_FIRST_TOKEN = re.compile(r"^\s*([A-Za-z]+)")
ORACLE_TEXT_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
ORACLE_TEXT_RESERVED = {
    "ABOUT",
    "ACCUM",
    "AND",
    "BT",
    "EQUIV",
    "FUZZY",
    "HASPATH",
    "INPATH",
    "MINUS",
    "NEAR",
    "NOT",
    "OR",
    "SQE",
    "SYN",
    "WITHIN",
}
FORBIDDEN_SQL_WORDS = {
    "ALTER",
    "ANALYZE",
    "BEGIN",
    "CALL",
    "COMMIT",
    "CREATE",
    "DECLARE",
    "DELETE",
    "DROP",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "INSERT",
    "LOCK",
    "MERGE",
    "REPLACE",
    "REVOKE",
    "ROLLBACK",
    "SAVEPOINT",
    "TRUNCATE",
    "UPDATE",
}


class SqlSafetyError(ValueError):
    """Raised when user SQL is outside the plugin's read-only safety envelope."""


@dataclass(frozen=True)
class SafeSql:
    sql: str


def bounded_int(value: Any, *, default: int, minimum: int, maximum: int, name: str) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def validate_identifier(identifier: str, *, label: str = "identifier") -> str:
    value = str(identifier or "").strip()
    if not value or len(value) > 128 or ORACLE_IDENTIFIER.fullmatch(value) is None:
        raise SqlSafetyError(f"Invalid Oracle {label}: {identifier}")
    return value


def validate_read_only_sql(sql: str) -> SafeSql:
    statement = str(sql or "").strip()
    if not statement:
        raise SqlSafetyError("SQL is required.")
    if "\x00" in statement:
        raise SqlSafetyError("SQL contains an invalid null byte.")
    if "--" in statement or "/*" in statement or "*/" in statement:
        raise SqlSafetyError("SQL comments are not allowed.")

    semicolon_count = statement.count(";")
    if semicolon_count > 1 or (semicolon_count == 1 and not statement.endswith(";")):
        raise SqlSafetyError("Only one SQL statement is allowed.")
    statement = statement[:-1].strip() if statement.endswith(";") else statement

    first_token_match = SQL_FIRST_TOKEN.match(statement)
    first_token = first_token_match.group(1).upper() if first_token_match else ""
    if first_token not in {"SELECT", "WITH"}:
        raise SqlSafetyError("Only SELECT or WITH read-only SQL is allowed.")

    normalized = re.sub(r"'(?:''|[^'])*'", "''", statement.upper())
    words = set(re.findall(r"\b[A-Z_]+\b", normalized))
    forbidden = sorted(words & FORBIDDEN_SQL_WORDS)
    if forbidden:
        raise SqlSafetyError(f"SQL contains forbidden keyword: {forbidden[0]}.")
    if re.search(r"\bFOR\s+UPDATE\b", normalized):
        raise SqlSafetyError("SELECT FOR UPDATE is not allowed.")
    if re.search(r"\bDBMS_[A-Z0-9_]*\b", normalized):
        raise SqlSafetyError("DBMS package calls are not allowed in read-only SQL.")

    return SafeSql(statement)


def parse_bind_parameters(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("bind_parameters must be a JSON object.") from exc
    if not isinstance(value, dict):
        raise ValueError("bind_parameters must be a JSON object.")

    binds: dict[str, Any] = {}
    for key, bind_value in value.items():
        bind_name = validate_identifier(str(key), label="bind parameter")
        binds[bind_name] = bind_value
    return binds


def parse_column_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_columns = [column.strip() for column in value.split(",")]
    elif isinstance(value, list):
        raw_columns = [str(column).strip() for column in value]
    else:
        raise SqlSafetyError("metadata_columns must be a comma-separated string or list.")
    return [validate_identifier(column, label="column name") for column in raw_columns if column]


def sanitize_oracle_text_query(query: str) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for raw_token in ORACLE_TEXT_TOKEN.findall(str(query or "")):
        token = raw_token.strip()
        normalized = token.casefold()
        if not token or normalized in seen or token.upper() in ORACLE_TEXT_RESERVED:
            continue
        seen.add(normalized)
        tokens.append(token)
    if not tokens:
        raise SqlSafetyError("Search query does not contain any safe Oracle Text tokens.")
    return " ACCUM ".join(tokens)


def build_external_search_sql(
    *,
    table_name: str,
    text_column: str,
    id_column: str,
    metadata_columns: list[str],
    use_oracle_text: bool,
) -> str:
    table = validate_identifier(table_name, label="table name")
    text_col = validate_identifier(text_column, label="text column")
    id_col = validate_identifier(id_column, label="ID column")
    selected_columns = [id_col, text_col, *metadata_columns]
    select_list = ", ".join(selected_columns)
    if use_oracle_text:
        return (
            f"SELECT {select_list}, SCORE(1) AS search_score FROM {table} "
            f"WHERE CONTAINS({text_col}, :query, 1) > 0 ORDER BY SCORE(1) DESC"
        )
    return f"SELECT {select_list} FROM {table} WHERE LOWER({text_col}) LIKE :query ESCAPE '\\'"
