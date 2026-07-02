from __future__ import annotations

import pytest

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from provider import oracle


def test_validation_error_redacts_and_suppresses_original_exception(monkeypatch):
    credentials = {"user": "app", "password": "secret", "dsn": "db/pdb"}

    class FailingClient:
        def ping(self):
            raise RuntimeError("Connection to db/pdb failed with password secret")

    monkeypatch.setattr(oracle.OracleDatabaseClient, "from_credentials", lambda _credentials: FailingClient())

    with pytest.raises(ToolProviderCredentialValidationError) as caught:
        oracle.OracleProvider()._validate_credentials(credentials)

    assert str(caught.value) == "Connection to [REDACTED] failed with password [REDACTED]"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
