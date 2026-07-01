from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from oracle_ai_database.sql_safety import (
    MAX_SEARCH_ROWS,
    bounded_float,
    bounded_int,
    build_external_hybrid_search_sql,
    parse_column_list,
    parse_vector,
    sanitize_oracle_text_query,
    validate_identifier,
)
from tools._shared import client_from_runtime, error_payload, require_text


def _like_query(query: str) -> str:
    escaped = query.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class HybridKnowledgeSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            query = require_text(tool_parameters.get("query"), name="query")
            query_vector = parse_vector(tool_parameters.get("query_vector"))
            table_name = validate_identifier(require_text(tool_parameters.get("table_name"), name="table_name"))
            text_column = validate_identifier(str(tool_parameters.get("text_column") or "text"), label="text column")
            vector_column = validate_identifier(
                str(tool_parameters.get("vector_column") or "embedding"),
                label="vector column",
            )
            content_column = validate_identifier(
                str(tool_parameters.get("content_column") or text_column),
                label="content column",
            )
            id_column = validate_identifier(str(tool_parameters.get("id_column") or "id"), label="ID column")
            metadata_columns = parse_column_list(tool_parameters.get("metadata_columns"))
            use_oracle_text = bool(tool_parameters.get("use_oracle_text", True))
            max_rows = bounded_int(
                tool_parameters.get("max_rows"),
                default=10,
                minimum=1,
                maximum=MAX_SEARCH_ROWS,
                name="max_rows",
            )
            vector_weight = bounded_float(
                tool_parameters.get("vector_weight"),
                default=0.7,
                minimum=0,
                maximum=1,
                name="vector_weight",
            )
            text_weight = bounded_float(
                tool_parameters.get("text_weight"),
                default=0.3,
                minimum=0,
                maximum=1,
                name="text_weight",
            )
            if vector_weight == 0 and text_weight == 0:
                raise ValueError("vector_weight and text_weight cannot both be 0.")

            candidate_rows = min(max_rows * 5, MAX_SEARCH_ROWS)
            sql = build_external_hybrid_search_sql(
                table_name=table_name,
                text_column=text_column,
                vector_column=vector_column,
                content_column=content_column,
                id_column=id_column,
                metadata_columns=metadata_columns,
                use_oracle_text=use_oracle_text,
                candidate_rows=candidate_rows,
            )
            bind_query = sanitize_oracle_text_query(query) if use_oracle_text else _like_query(query)
            result = client_from_runtime(self).execute_hybrid_search(
                sql,
                query=bind_query,
                query_vector=query_vector,
                vector_weight=vector_weight,
                text_weight=text_weight,
                max_rows=max_rows,
            )
            payload = result.to_dict()
            payload["mode"] = "oracle_hybrid"
            payload["text_mode"] = "oracle_text" if use_oracle_text else "like"
            payload["distance_metric"] = "cosine"
            payload["vector_weight"] = vector_weight
            payload["text_weight"] = text_weight
            yield self.create_json_message(payload)
        except Exception as exc:
            yield self.create_json_message(error_payload(exc))
