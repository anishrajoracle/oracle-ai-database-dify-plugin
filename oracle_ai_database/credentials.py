from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CredentialError(ValueError):
    """Raised when Oracle provider credentials are incomplete or invalid."""


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class OracleCredentials:
    user: str
    password: str
    dsn: str
    config_dir: str | None = None
    wallet_location: str | None = None
    wallet_password: str | None = None

    @classmethod
    def from_mapping(cls, credentials: dict[str, Any]) -> OracleCredentials:
        user = _clean_optional(credentials.get("user"))
        password = _clean_optional(credentials.get("password"))
        if not user:
            raise CredentialError("Oracle user is required.")
        if not password:
            raise CredentialError("Oracle password is required.")

        dsn = _clean_optional(credentials.get("dsn"))
        if not dsn:
            host = _clean_optional(credentials.get("host"))
            service_name = _clean_optional(credentials.get("service_name"))
            port = _clean_optional(credentials.get("port")) or "1521"
            if not host:
                raise CredentialError("Oracle DSN or host is required.")
            if not service_name:
                raise CredentialError("Oracle DSN or service_name is required.")
            try:
                port_number = int(port)
            except ValueError as exc:
                raise CredentialError("Oracle port must be an integer.") from exc
            if port_number <= 0 or port_number > 65535:
                raise CredentialError("Oracle port must be between 1 and 65535.")
            dsn = f"{host}:{port_number}/{service_name}"

        return cls(
            user=user,
            password=password,
            dsn=dsn,
            config_dir=_clean_optional(credentials.get("config_dir")),
            wallet_location=_clean_optional(credentials.get("wallet_location")),
            wallet_password=_clean_optional(credentials.get("wallet_password")),
        )

    def connect_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "user": self.user,
            "password": self.password,
            "dsn": self.dsn,
        }
        if self.config_dir:
            kwargs["config_dir"] = self.config_dir
        if self.wallet_location:
            kwargs["wallet_location"] = self.wallet_location
        if self.wallet_password:
            kwargs["wallet_password"] = self.wallet_password
        return kwargs

