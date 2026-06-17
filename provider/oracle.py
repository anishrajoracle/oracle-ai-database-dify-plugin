from __future__ import annotations

from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from oracle_ai_database.client import OracleDatabaseClient


class OracleProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            OracleDatabaseClient.from_credentials(credentials).ping()
        except Exception as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc

