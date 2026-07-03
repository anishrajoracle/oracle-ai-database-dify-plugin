from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from oracle_ai_database.sql_safety import (
    MAX_WRITE_ROWS,
    bounded_int,
    parse_identifier_allowlist,
    parse_write_bind_parameters,
    validate_write_only_sql,
)
from tools._shared import client_from_runtime, credentials_from_runtime, error_payload, require_text


class WriteOnlySqlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            if credentials_from_runtime(self).get("enable_writes") is not True:
                raise ValueError("Write execution is disabled. Enable it explicitly in the provider authorization.")

            sql = require_text(tool_parameters.get("sql"), name="sql")
            allowed_tables = parse_identifier_allowlist(tool_parameters.get("allowed_tables"))
            allow_delete = tool_parameters.get("allow_delete") is True
            safe_sql = validate_write_only_sql(
                sql,
                allowed_tables=allowed_tables,
                allow_delete=allow_delete,
            )
            binds = parse_write_bind_parameters(safe_sql.sql, tool_parameters.get("bind_parameters"))
            max_affected_rows = bounded_int(
                tool_parameters.get("max_affected_rows"),
                default=1,
                minimum=1,
                maximum=MAX_WRITE_ROWS,
                name="max_affected_rows",
            )

            result = client_from_runtime(self).execute_write_only(
                safe_sql.sql,
                binds=binds,
                allowed_tables=allowed_tables,
                allow_delete=allow_delete,
                max_affected_rows=max_affected_rows,
            )
            yield self.create_json_message(result.to_dict())
        except Exception as exc:
            yield self.create_json_message(error_payload(exc, tool=self))
