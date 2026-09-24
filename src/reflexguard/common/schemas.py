"""Version 1 brain API contracts, shared by mock and future brain servers."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ID_PATTERN = r"^[A-Za-z0-9_-][A-Za-z0-9_.:-]*$"
Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=ID_PATTERN)]
UnitFloat = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always",
        hide_input_in_errors=True,
    )


class HealthResponse(ContractModel):
    status: Literal["ok"]
    model_version: Annotated[str, Field(min_length=1, max_length=128)]
    weights_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class CreateSessionRequest(ContractModel):
    """Session creation accepts an empty body or an empty JSON object."""


class SessionResponse(ContractModel):
    session_id: Identifier


class StepRequest(ContractModel):
    t_ms: Annotated[int, Field(ge=0)]
    dt_ms: Annotated[int, Field(ge=1, le=100)]
    left_looming: UnitFloat
    right_looming: UnitFloat


class NeuronActivity(ContractModel):
    id: Identifier
    type: Annotated[str, Field(min_length=1, max_length=128)]
    rate_hz: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class StepResponse(ContractModel):
    escape: UnitFloat
    turn_left: UnitFloat
    turn_right: UnitFloat
    top_neurons: Annotated[list[NeuronActivity], Field(max_length=64)]
    model_version: Annotated[str, Field(min_length=1, max_length=128)]


class SilenceRequest(ContractModel):
    neuron_ids: Annotated[list[Identifier], Field(max_length=10)]

    @field_validator("neuron_ids")
    @classmethod
    def unique_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Neuron IDs must be unique")
        return value


class SilenceResponse(ContractModel):
    accepted: Annotated[list[Identifier], Field(max_length=10)]
