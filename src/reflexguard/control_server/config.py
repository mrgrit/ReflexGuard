"""Configuration is trusted local deployment input, never request input."""
import os
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from reflexguard.common.config import ClientSettings, TokenRecord
from reflexguard.common.schemas import Identifier

class Device(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    chair_id: Identifier
    token: SecretStr
    hmac_key: SecretStr

    @field_validator("token", "hmac_key")
    @classmethod
    def strong_secret(cls, value):
        return TokenRecord.strong_token(value)

class ControlSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    origin: str = "https://localhost:8444"
    database: Path
    devices: Annotated[list[Device], Field(min_length=1, max_length=256)]
    audit_key: SecretStr

    @field_validator("audit_key")
    @classmethod
    def strong_secret(cls, value):
        return TokenRecord.strong_token(value)

    @field_validator("origin")
    @classmethod
    def valid_origin(cls, value):
        from pydantic import AnyHttpUrl, TypeAdapter
        url=TypeAdapter(AnyHttpUrl).validate_python(value)
        ClientSettings.https_origin_only(url)
        return str(url).rstrip("/")

    @model_validator(mode="after")
    def unique_devices(self):
        ids=[x.chair_id for x in self.devices]
        keys=[x.token.get_secret_value() for x in self.devices]+[x.hmac_key.get_secret_value() for x in self.devices]+[self.audit_key.get_secret_value()]
        if len(ids)!=len(set(ids)) or len(keys)!=len(set(keys)):
            raise ValueError("Device identifiers and credentials must be distinct")
        return self

    @classmethod
    def from_env(cls):
        import json
        return cls(origin=os.environ.get("REFLEXGUARD_CONTROL_URL", "https://localhost:8444"),
                   database=Path(os.environ.get("REFLEXGUARD_CONTROL_DB", "control.db")),
                   devices=json.loads(os.environ["REFLEXGUARD_CONTROL_DEVICES"]),
                   audit_key=os.environ["REFLEXGUARD_AUDIT_KEY"])
