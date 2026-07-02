from __future__ import annotations

import sys
import types


class _StubTool:
    def create_json_message(self, payload, suppress_output: bool = False):
        return {
            "type": "json",
            "json": payload,
            "suppress_output": suppress_output,
        }

    def create_text_message(self, text: str):
        return {
            "type": "text",
            "text": text,
        }

    def create_variable_message(self, name: str, value):
        return {
            "type": "variable",
            "name": name,
            "value": value,
        }


class _StubToolProvider:
    pass


class _StubPlugin:
    def __init__(self, env):
        self.env = env

    def run(self):
        return None


class _StubDifyPluginEnv:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _StubToolProviderCredentialValidationError(Exception):
    pass


dify_plugin = types.ModuleType("dify_plugin")
dify_plugin.Tool = _StubTool
dify_plugin.ToolProvider = _StubToolProvider
dify_plugin.Plugin = _StubPlugin
dify_plugin.DifyPluginEnv = _StubDifyPluginEnv

entities = types.ModuleType("dify_plugin.entities")
tool_entities = types.ModuleType("dify_plugin.entities.tool")
tool_entities.ToolInvokeMessage = dict

errors = types.ModuleType("dify_plugin.errors")
tool_errors = types.ModuleType("dify_plugin.errors.tool")
tool_errors.ToolProviderCredentialValidationError = _StubToolProviderCredentialValidationError

sys.modules.setdefault("dify_plugin", dify_plugin)
sys.modules.setdefault("dify_plugin.entities", entities)
sys.modules.setdefault("dify_plugin.entities.tool", tool_entities)
sys.modules.setdefault("dify_plugin.errors", errors)
sys.modules.setdefault("dify_plugin.errors.tool", tool_errors)
