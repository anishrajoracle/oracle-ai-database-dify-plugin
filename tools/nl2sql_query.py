from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from oracle_ai_database.sql_safety import MAX_READ_ROWS, bounded_int, validate_read_only_sql
from tools._shared import (
    client_from_runtime,
    error_payload,
    extract_sql_from_select_ai_response,
    require_text,
    validate_select_ai_profile,
)


class Nl2SqlQueryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            question = require_text(tool_parameters.get("question"), name="question")
            profile_name = validate_select_ai_profile(tool_parameters.get("profile_name"))
            execute = bool(tool_parameters.get("execute", False))
            max_rows = bounded_int(
                tool_parameters.get("max_rows"),
                default=100,
                minimum=1,
                maximum=MAX_READ_ROWS,
                name="max_rows",
            )

            client = client_from_runtime(self)
            generated = client.select_ai(prompt=question, profile_name=profile_name, action="showsql")
            generated_sql = extract_sql_from_select_ai_response(generated)
            safe_sql = validate_read_only_sql(generated_sql)
            payload: dict[str, Any] = {
                "status": "success",
                "profile_name": profile_name,
                "generated_sql": safe_sql.sql,
                "executed": execute,
            }
            if execute:
                payload["result"] = client.execute_read_only(safe_sql, binds={}, max_rows=max_rows).to_dict()
            yield self.create_json_message(payload)
        except Exception as exc:
            yield self.create_json_message(error_payload(exc))

