import math

from pydantic import ValidationError
import pytest

from reflexguard.common.schemas import (
    HealthResponse, NeuronActivity, SessionResponse, SilenceRequest, StepRequest, StepResponse,
)

VALID_STEP = {"t_ms": 0, "dt_ms": 50, "left_looming": 0.0, "right_looming": 1.0}


@pytest.mark.parametrize("field,value", [
    ("t_ms", -1), ("t_ms", True), ("t_ms", "0"), ("t_ms", 0.5),
    ("dt_ms", 0), ("dt_ms", 101), ("dt_ms", True), ("dt_ms", "50"),
    ("left_looming", -0.01), ("right_looming", 1.01),
    ("left_looming", math.nan), ("right_looming", math.inf),
    ("left_looming", True), ("right_looming", "0.5"),
])
def test_step_rejects_invalid_ranges_and_types(field, value):
    with pytest.raises(ValidationError):
        StepRequest.model_validate({**VALID_STEP, field: value})


@pytest.mark.parametrize("dt", [1, 100])
def test_step_accepts_contract_boundaries(dt):
    assert StepRequest(**{**VALID_STEP, "dt_ms": dt}).dt_ms == dt


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        StepRequest(**VALID_STEP, extra="ignored input is forbidden")


@pytest.mark.parametrize("ids", [[str(i) for i in range(11)], ["a", "a"], ["../a"], [""]])
def test_silence_rejects_invalid_lists(ids):
    with pytest.raises(ValidationError):
        SilenceRequest(neuron_ids=ids)


def test_empty_silence_clears_selection_and_ten_is_allowed():
    assert SilenceRequest(neuron_ids=[]).neuron_ids == []
    assert len(SilenceRequest(neuron_ids=[str(i) for i in range(10)]).neuron_ids) == 10


def test_response_bounds_and_finiteness():
    for value in (-1.0, math.inf, math.nan):
        with pytest.raises(ValidationError):
            NeuronActivity(id="mock-a", type="mock", rate_hz=value)
    with pytest.raises(ValidationError):
        StepResponse(escape=1.1, turn_left=0.0, turn_right=0.0, top_neurons=[], model_version="v1")
    with pytest.raises(ValidationError):
        HealthResponse(status="ok", model_version="v1", weights_sha256="invalid")
    with pytest.raises(ValidationError):
        SessionResponse(session_id="../../another-session")
