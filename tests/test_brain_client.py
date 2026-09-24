import asyncio
import logging
import time

import httpx
from pydantic import ValidationError
import pytest

from reflexguard.brain_client.client import BrainClient, BrainClientError, MAX_RESPONSE_BYTES
from reflexguard.common.config import ClientSettings, ConfigurationError, MockSettings
from reflexguard.common.schemas import StepRequest


def use_transport(monkeypatch, handler):
    original = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_client_validates_response_and_sends_bearer(client_settings, monkeypatch):
    def handler(request):
        assert request.headers["Authorization"] == "Bearer " + client_settings.token.get_secret_value()
        assert request.url.scheme == "https"
        return httpx.Response(200, json={"session_id": "session-a"})

    use_transport(monkeypatch, handler)

    async def run():
        async with BrainClient(client_settings) as client:
            assert (await client.create_session()).session_id == "session-a"

    asyncio.run(run())


@pytest.mark.parametrize("response", [
    httpx.Response(500, text="private response contents"),
    httpx.Response(200, text="not-json"),
    httpx.Response(200, json={"status": "ok"}),
    httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1)),
    httpx.Response(307, headers={"Location": "https://another-service.invalid"}),
    httpx.Response(200, stream=httpx.ByteStream(b"not-expanded"), headers={"Content-Encoding": "gzip"}),
])
def test_untrusted_responses_raise_generic_error(client_settings, monkeypatch, caplog, response):
    calls = []

    def handler(request):
        calls.append(request.url)
        return response

    use_transport(monkeypatch, handler)

    async def run():
        async with BrainClient(client_settings) as client:
            with pytest.raises(BrainClientError, match="^Brain service unavailable$"):
                await client.health()

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert len(calls) == 1
    assert "private response contents" not in caplog.text
    assert client_settings.token.get_secret_value() not in caplog.text


def test_connection_failure_is_not_retried(client_settings, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("connection unavailable")

    use_transport(monkeypatch, handler)

    async def run():
        async with BrainClient(client_settings) as client:
            with pytest.raises(BrainClientError):
                await client.health()

    asyncio.run(run())
    assert len(calls) == 1


def test_total_deadline_stops_slow_drip_response(client_settings, monkeypatch):
    closed = []

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(10):
                await asyncio.sleep(0.08)
                yield b" "

        async def aclose(self):
            closed.append(True)

    use_transport(monkeypatch, lambda request: httpx.Response(200, stream=SlowStream()))

    async def run():
        async with BrainClient(client_settings) as client:
            start = time.monotonic()
            with pytest.raises(BrainClientError):
                await client.health()
            elapsed = time.monotonic() - start
            # Allow CI scheduling jitter while distinguishing the 0.8s full body.
            assert 0.15 <= elapsed < 0.65

    asyncio.run(run())
    assert closed == [True]


@pytest.mark.parametrize("invalid_id", ["../../v1/health", ".", ".."])
def test_invalid_session_id_is_rejected_before_network(client_settings, monkeypatch, invalid_id):
    def handler(request):
        pytest.fail("Invalid ID must not reach the network")

    use_transport(monkeypatch, handler)

    async def run():
        async with BrainClient(client_settings) as client:
            with pytest.raises(ValidationError):
                await client.step(invalid_id, StepRequest(
                    t_ms=0, dt_ms=50, left_looming=0.0, right_looming=0.0,
                ))

    asyncio.run(run())


@pytest.mark.parametrize("url", [
    "http://localhost", "https://localhost/path", "https://localhost?query=1",
    "https://localhost#fragment", "https://user@localhost",
])
def test_client_origin_is_https_without_ambiguous_components(client_settings, url):
    with pytest.raises(ValidationError):
        ClientSettings.model_validate({**client_settings.model_dump(), "base_url": url})


def test_missing_environment_fails_closed(monkeypatch, caplog):
    monkeypatch.delenv("REFLEXGUARD_API_TOKENS", raising=False)
    with pytest.raises(ConfigurationError):
        MockSettings.from_env()
    monkeypatch.setenv("REFLEXGUARD_API_TOKENS", "invalid-private-marker")
    with pytest.raises(ConfigurationError) as error:
        MockSettings.from_env()
    assert "invalid-private-marker" not in str(error.value)
    assert "invalid-private-marker" not in caplog.text


def test_missing_tls_file_fails_before_connecting(client_settings, tmp_path):
    with pytest.raises(ValidationError):
        ClientSettings.model_validate({**client_settings.model_dump(), "ca_cert": tmp_path / "missing"})
