from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._shared import (
    client_from_runtime,
    error_payload,
    require_text,
    validate_select_ai_action,
    validate_select_ai_profile,
)


class SelectAiQueryTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            prompt = require_text(tool_parameters.get("prompt"), name="prompt")
            profile_name = validate_select_ai_profile(tool_parameters.get("profile_name"))
            action = validate_select_ai_action(tool_parameters.get("action"))
            response = client_from_runtime(self).select_ai(
                prompt=prompt,
                profile_name=profile_name,
                action=action,
            )
            yield self.create_json_message(
                {
                    "status": "success",
                    "action": action,
                    "profile_name": profile_name,
                    "response": response,
                }
            )
        except Exception as exc:
            yield self.create_json_message(error_payload(exc))

