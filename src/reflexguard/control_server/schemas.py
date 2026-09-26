"""Bounded external contracts for supervisory control."""
from typing import Annotated, Literal
from pydantic import Field, SecretStr, field_validator, model_validator
from reflexguard.common.schemas import ContractModel, Identifier, UnitFloat, NeuronActivity, SilenceRequest

Name = Annotated[str, Field(min_length=1, max_length=80)]
Nonce = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{32,128}$")]
Role = Literal["guardian", "operator", "admin"]

class Login(ContractModel):
    username: Name
    password: SecretStr

    @field_validator("password")
    @classmethod
    def password_length(cls, value):
        if not 12 <= len(value.get_secret_value().encode()) <= 72:
            raise ValueError("Password must contain 12..72 UTF-8 bytes")
        return value

class UserCreate(Login):
    role: Role

class UserUpdate(ContractModel):
    role: Role
    active: bool

class Assignment(ContractModel):
    guardian_id: Annotated[int, Field(gt=0)]

class RemoteRequest(ContractModel):
    chair_id: Identifier
    action: Literal["stop", "speed_limit"]
    speed_limit: Annotated[float, Field(ge=0, le=0.6, allow_inf_nan=False)] | None = None

    @model_validator(mode="after")
    def action_value(self):
        if (self.action == "speed_limit") != (self.speed_limit is not None):
            raise ValueError("Speed limit required only for speed_limit action")
        return self

class RemoteBody(RemoteRequest):
    boot_id: Nonce
    nonce: Nonce
    issued_ms: Annotated[int, Field(ge=0)]

class SignedRemote(ContractModel):
    body: RemoteBody
    signature: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

class Hello(ContractModel):
    boot_id: Nonce

class DecisionInput(ContractModel):
    neuron_activity: Annotated[list[NeuronActivity], Field(max_length=256)] = []
    weights_sha256: Annotated[str, Field(pattern=r"^([0-9a-f]{64})?$")] = ""
    navigation_mode: Literal["reflex_stop", "range_assisted"] = "reflex_stop"
    boot_id: Nonce
    sequence: Annotated[int, Field(ge=1)]
    t_ms: Annotated[int, Field(ge=0)]
    left_looming: UnitFloat
    right_looming: UnitFloat
    escape: UnitFloat
    top_neurons: Annotated[list[NeuronActivity], Field(max_length=64)]
    model_version: Annotated[str, Field(min_length=1, max_length=128)]
    reason: Annotated[str, Field(min_length=1, max_length=128)]
    forward: Annotated[float, Field(ge=-6.0, le=6.0, allow_inf_nan=False)]
    turn: Annotated[float, Field(ge=-2, le=2, allow_inf_nan=False)]
    remote_stopped: bool

class DevicePoll(ContractModel):
    boot_id: Nonce
    acknowledged: Nonce | None = None

class PollResponse(ContractModel):
    command: SignedRemote | None
    silence: SilenceRequest | None
