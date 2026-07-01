from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from oracle_ai_database.sql_safety import (
    MAX_READ_ROWS,
    bounded_int,
    has_bind_placeholders,
    parse_bind_parameters,
)
from tools._shared import client_from_runtime, error_payload, require_text


class ReadOnlySqlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            sql = require_text(tool_parameters.get("sql"), name="sql")
            bind_parameters = tool_parameters.get("bind_parameters")
            if not has_bind_placeholders(sql) and bind_parameters not in (None, ""):
                bind_parameters = None
            binds = parse_bind_parameters(bind_parameters)
            max_rows = bounded_int(
                tool_parameters.get("max_rows"),
                default=100,
                minimum=1,
                maximum=MAX_READ_ROWS,
                name="max_rows",
            )
            result = client_from_runtime(self).execute_read_only(sql, binds=binds, max_rows=max_rows)
            yield self.create_json_message(result.to_dict())
        except Exception as exc:
            yield self.create_json_message(error_payload(exc))
