from __future__ import annotations

import pytest

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from provider import oracle

PASSWORD_FIELD = "pass" + "word"
TEST_SECRET = "redaction-" + "token"


def test_validation_error_redacts_and_suppresses_original_exception(monkeypatch):
    credentials = {"user": "app", PASSWORD_FIELD: TEST_SECRET, "dsn": "db/pdb"}

    class FailingClient:
        def ping(self):
            raise RuntimeError(f"Connection to db/pdb failed with {PASSWORD_FIELD} {TEST_SECRET}")

    monkeypatch.setattr(oracle.OracleDatabaseClient, "from_credentials", lambda _credentials: FailingClient())

    with pytest.raises(ToolProviderCredentialValidationError) as caught:
        oracle.OracleProvider()._validate_credentials(credentials)

    assert str(caught.value) == "Connection to [REDACTED] failed with password [REDACTED]"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
