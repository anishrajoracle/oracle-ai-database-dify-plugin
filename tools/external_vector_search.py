from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from oracle_ai_database.sql_safety import (
    MAX_SEARCH_ROWS,
    bounded_int,
    build_external_vector_search_sql,
    parse_column_list,
    parse_vector,
    validate_identifier,
)
from tools._shared import client_from_runtime, error_payload, require_text


class ExternalVectorSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            query_vector = parse_vector(tool_parameters.get("query_vector"))
            table_name = validate_identifier(require_text(tool_parameters.get("table_name"), name="table_name"))
            vector_column = validate_identifier(
                str(tool_parameters.get("vector_column") or "embedding"),
                label="vector column",
            )
            content_column = validate_identifier(
                str(tool_parameters.get("content_column") or "text"),
                label="content column",
            )
            id_column = validate_identifier(str(tool_parameters.get("id_column") or "id"), label="ID column")
            metadata_columns = parse_column_list(tool_parameters.get("metadata_columns"))
            max_rows = bounded_int(
                tool_parameters.get("max_rows"),
                default=10,
                minimum=1,
                maximum=MAX_SEARCH_ROWS,
                name="max_rows",
            )

            sql = build_external_vector_search_sql(
                table_name=table_name,
                vector_column=vector_column,
                content_column=content_column,
                id_column=id_column,
                metadata_columns=metadata_columns,
            )
            result = client_from_runtime(self).execute_vector_search(
                sql,
                query_vector=query_vector,
                max_rows=max_rows,
            )
            payload = result.to_dict()
            payload["mode"] = "oracle_vector"
            payload["distance_metric"] = "cosine"
            yield self.create_json_message(payload)
        except Exception as exc:
            yield self.create_json_message(error_payload(exc, tool=self))
