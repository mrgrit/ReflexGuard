"""Environment configuration; never include secret values in diagnostics."""

import logging
import os
import re
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl, BaseModel, ConfigDict, Field, FilePath, SecretStr,
    TypeAdapter, ValidationError, field_validator, model_validator,
)

from reflexguard.common.schemas import Identifier

LOGGER = logging.getLogger(__name__)
BEARER_PATTERN = r"^[A-Za-z0-9_-]{32,256}$"
Role = Literal["guardian", "operator", "admin"]


class ConfigurationError(RuntimeError):
    """Configuration is missing or invalid; no secret values are exposed."""


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)


class TokenRecord(ConfigModel):
    token: SecretStr
    subject: Identifier
    role: Role

    @field_validator("token")
    @classmethod
    def strong_token(cls, value):
        if not re.fullmatch(BEARER_PATTERN, value.get_secret_value()):
            raise ValueError("Use a secrets-generated URL-safe token of at least 32 characters")
        return value


class MockSettings(ConfigModel):
    tokens: Annotated[list[TokenRecord], Field(min_length=1, max_length=32)]
    max_sessions: Annotated[int, Field(ge=1, le=1024)] = 256
    session_ttl_seconds: Annotated[int, Field(ge=1, le=3600)] = 900

    @model_validator(mode="after")
    def unique_tokens(self):
        values = [entry.token.get_secret_value() for entry in self.tokens]
        if len(values) != len(set(values)):
            raise ValueError("API tokens must be unique")
        return self

    @classmethod
    def from_env(cls):
        raw = os.environ.get("REFLEXGUARD_API_TOKENS", "")
        try:
            records = TypeAdapter(list[TokenRecord]).validate_json(raw)
            return cls(tokens=records)
        except ValidationError:
            LOGGER.error("Invalid REFLEXGUARD_API_TOKENS configuration")
            raise ConfigurationError("Invalid brain service configuration") from None


class ServerTLSSettings(ConfigModel):
    ca_cert: FilePath
    server_cert: FilePath
    server_key: FilePath
    port: Annotated[int, Field(ge=1024, le=65535)] = 8443

    @classmethod
    def from_env(cls):
        try:
            return cls.model_validate({
                "ca_cert": os.environ.get("REFLEXGUARD_TLS_CA"),
                "server_cert": os.environ.get("REFLEXGUARD_TLS_SERVER_CERT"),
                "server_key": os.environ.get("REFLEXGUARD_TLS_SERVER_KEY"),
                "port": os.environ.get("REFLEXGUARD_MOCK_PORT", "8443"),
            })
        except ValidationError:
            LOGGER.error("Missing or invalid server TLS configuration")
            raise ConfigurationError("Invalid server TLS configuration") from None


class ClientSettings(ConfigModel):
    base_url: AnyHttpUrl
    token: SecretStr
    ca_cert: FilePath
    client_cert: FilePath
    client_key: FilePath

    @field_validator("token")
    @classmethod
    def strong_token(cls, value):
        return TokenRecord.strong_token(value)

    @field_validator("base_url")
    @classmethod
    def https_origin_only(cls, value):
        if (value.scheme != "https" or value.username or value.password
                or value.query or value.fragment or value.path not in (None, "", "/")):
            raise ValueError("Use an HTTPS origin without credentials, path, query or fragment")
        return value

    @classmethod
    def from_env(cls):
        try:
            return cls.model_validate({
                "base_url": os.environ.get("REFLEXGUARD_BRAIN_URL"),
                "token": os.environ.get("REFLEXGUARD_BRAIN_TOKEN"),
                "ca_cert": os.environ.get("REFLEXGUARD_TLS_CA"),
                "client_cert": os.environ.get("REFLEXGUARD_TLS_CLIENT_CERT"),
                "client_key": os.environ.get("REFLEXGUARD_TLS_CLIENT_KEY"),
            })
        except ValidationError:
            LOGGER.error("Missing or invalid brain client environment configuration")
            raise ConfigurationError("Invalid brain client configuration") from None
