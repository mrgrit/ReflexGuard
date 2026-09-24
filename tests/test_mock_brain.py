import secrets

from fastapi import HTTPException
import pytest

from reflexguard.common.schemas import HealthResponse, StepResponse
from reflexguard.mock_brain.security import MAX_REQUEST_BYTES
from reflexguard.mock_brain.store import SessionStore


def new_session(api):
    result = api.post("/v1/sessions")
    assert result.status_code == 200
    return result.json()["session_id"]


def step(api, session, left=0.9, right=0.1, time=0):
    return api.post(f"/v1/sessions/{session}/step", json={
        "t_ms": time, "dt_ms": 50, "left_looming": left, "right_looming": right,
    })


def test_health_and_session_contract(api):
    response = api.get("/v1/health")
    health = HealthResponse.model_validate(response.json())
    assert health.status == "ok"
    assert health.model_version.startswith("mock-")
    assert response.headers["cache-control"] == "no-store"
    assert new_session(api) != new_session(api)


@pytest.mark.parametrize("left,right,direction", [(1.0, 0.0, "turn_right"), (0.0, 1.0, "turn_left")])
def test_looming_causes_escape_and_opposite_turn(api, left, right, direction):
    response = step(api, new_session(api), left, right)
    assert response.status_code == 200
    result = StepResponse.model_validate(response.json())
    assert result.escape == 1.0
    assert getattr(result, direction) == 1.0
    assert all(n.type == "mock" for n in result.top_neurons)


def test_low_looming_is_inactive_and_symmetric_looming_has_no_turn(api):
    session = new_session(api)
    low = step(api, session, 0.2, 0.1).json()
    assert (low["escape"], low["turn_left"], low["turn_right"]) == (0.0, 0.0, 0.0)
    high = step(api, session, 1.0, 1.0, time=50).json()
    assert (high["escape"], high["turn_left"], high["turn_right"]) == (1.0, 0.0, 0.0)


def test_all_endpoints_require_valid_bearer(api):
    api.headers.pop("Authorization")
    for method, path in [("GET", "/v1/health"), ("POST", "/v1/sessions"),
                         ("POST", "/v1/sessions/a/step"), ("POST", "/v1/sessions/a/silence")]:
        assert api.request(method, path).status_code == 401
    api.headers["Authorization"] = "Bearer " + secrets.token_urlsafe(32)
    assert api.get("/v1/health").status_code == 401


def test_duplicate_authorization_is_rejected(api, credentials):
    token = credentials["operator"]["token"]
    assert api.get("/v1/health", headers=[("Authorization", "Bearer " + token)] * 2).status_code == 401


def test_plain_http_cannot_be_upgraded_with_forwarded_header(api):
    assert api.get("http://localhost/v1/health", headers={"X-Forwarded-Proto": "https"}).status_code == 400


def test_sessions_are_owned_and_missing_sessions_are_indistinguishable(api, credentials):
    session = new_session(api)
    api.headers["Authorization"] = "Bearer " + credentials["outsider"]["token"]
    denied = step(api, session)
    missing = step(api, "missing")
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()
    assert api.post(f"/v1/sessions/{session}/silence", json={"neuron_ids": []}).status_code == 404


@pytest.mark.parametrize("role,status", [("guardian", 403), ("operator", 200), ("admin", 200)])
def test_silence_role_permissions(api, credentials, role, status):
    session = new_session(api)
    api.headers["Authorization"] = "Bearer " + credentials[role]["token"]
    result = api.post(f"/v1/sessions/{session}/silence", json={"neuron_ids": ["mock-escape"]})
    assert result.status_code == status


def test_silence_changes_output_and_can_be_cleared(api):
    session = new_session(api)
    endpoint = f"/v1/sessions/{session}/silence"
    assert api.post(endpoint, json={"neuron_ids": ["mock-escape"]}).json() == {"accepted": ["mock-escape"]}
    result = step(api, session).json()
    assert result["escape"] == 0.0
    assert result["turn_right"] > 0
    assert api.post(endpoint, json={"neuron_ids": []}).status_code == 200
    assert step(api, session, time=50).json()["escape"] > 0


def test_invalid_silence_is_atomic_and_sessions_are_independent(api):
    a, b = new_session(api), new_session(api)
    endpoint = f"/v1/sessions/{a}/silence"
    assert api.post(endpoint, json={"neuron_ids": ["mock-escape", "not-allowed"]}).status_code == 422
    assert step(api, a).json()["escape"] > 0
    api.post(endpoint, json={"neuron_ids": ["mock-escape"]})
    assert step(api, b).json()["escape"] > 0
    assert step(api, a, time=50).json()["escape"] == 0
    assert api.post(endpoint, json={"neuron_ids": [str(i) for i in range(11)]}).status_code == 422


def test_timestamp_replay_is_rejected_without_advancing_state(api):
    session = new_session(api)
    assert step(api, session, time=50).status_code == 200
    assert step(api, session, time=50).status_code == 409
    assert step(api, session, time=0).status_code == 409
    assert step(api, session, time=100).status_code == 200


def test_errors_do_not_echo_input_and_requests_are_bounded(api):
    result = api.post("/v1/sessions", json={"private-marker": "not an allowed field"})
    assert result.status_code == 422
    assert result.json() == {"detail": "Invalid request"}
    assert api.post("/v1/sessions", content=b"x" * (MAX_REQUEST_BYTES + 1)).status_code == 413
    assert api.get("/docs").status_code == 404
    assert api.get("/openapi.json").status_code == 404


def test_unexpected_errors_are_generic_but_logged(api, monkeypatch, caplog):
    session = new_session(api)

    def fail(*args):
        raise RuntimeError("internal-diagnostic-marker")

    monkeypatch.setattr(api.app.state.sessions, "step", fail)
    result = step(api, session)
    assert result.status_code == 500
    assert result.json() == {"detail": "Service unavailable"}
    assert "internal-diagnostic-marker" in caplog.text


def test_session_capacity_and_expiry():
    clock = [0.0]
    store = SessionStore(1, 5, clock=lambda: clock[0])
    first = store.create("owner")
    with pytest.raises(HTTPException) as error:
        store.create("owner")
    assert error.value.status_code == 503
    clock[0] = 5.0
    assert store.create("owner") != first
