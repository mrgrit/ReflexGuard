"""No retries or silent fallback: callers must safely stop on BrainClientError."""

import asyncio
import logging
import ssl
from typing import TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from reflexguard.common.config import ClientSettings, ConfigurationError
from reflexguard.common.schemas import (
    HealthResponse, Identifier, SessionResponse, SilenceRequest, SilenceResponse,
    StepRequest, StepResponse,
)

LOGGER = logging.getLogger(__name__)
TIMEOUT_SECONDS = 0.2
MAX_RESPONSE_BYTES = 64 * 1024
MODEL = TypeVar("MODEL", bound=BaseModel)
SESSION_ID = TypeAdapter(Identifier)


class BrainClientError(RuntimeError):
    """The brain response cannot be trusted or did not arrive in time."""


class BrainClient:
    def __init__(self, settings: ClientSettings | None = None):
        self.settings = settings if settings is not None else ClientSettings.from_env()
        try:
            context = ssl.create_default_context(cafile=str(self.settings.ca_cert))
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(
                certfile=str(self.settings.client_cert), keyfile=str(self.settings.client_key),
            )
        except (OSError, ssl.SSLError):
            LOGGER.error("Unable to load brain client TLS credentials")
            raise ConfigurationError("Invalid brain client TLS credentials") from None
        self._client = httpx.AsyncClient(
            base_url=str(self.settings.base_url), verify=context,
            headers={
                "Authorization": "Bearer " + self.settings.token.get_secret_value(),
                "Accept-Encoding": "identity",
            },
            timeout=httpx.Timeout(TIMEOUT_SECONDS), trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    async def _exchange(self, method, path, model: type[MODEL], body):
        async with self._client.stream(method, path, json=body) as response:
            response.raise_for_status()
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise BrainClientError("Compressed brain responses are not accepted")
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise BrainClientError("Brain response exceeds size limit")
            return model.model_validate_json(bytes(content))

    async def _request(self, method, path, model: type[MODEL], body=None) -> MODEL:
        try:
            return await asyncio.wait_for(
                self._exchange(method, path, model, body), timeout=TIMEOUT_SECONDS,
            )
        except (httpx.HTTPError, ValidationError, asyncio.TimeoutError, BrainClientError) as exc:
            LOGGER.warning("Brain request failed (%s)", type(exc).__name__)
            raise BrainClientError("Brain service unavailable") from None

    async def health(self) -> HealthResponse:
        return await self._request("GET", "/v1/health", HealthResponse)

    async def create_session(self) -> SessionResponse:
        return await self._request("POST", "/v1/sessions", SessionResponse)

    async def step(self, session_id: str, request: StepRequest) -> StepResponse:
        session_id = SESSION_ID.validate_python(session_id)
        request = StepRequest.model_validate(request)
        return await self._request(
            "POST", f"/v1/sessions/{session_id}/step", StepResponse, request.model_dump(),
        )

    async def silence(self, session_id: str, neuron_ids: list[str]) -> SilenceResponse:
        session_id = SESSION_ID.validate_python(session_id)
        request = SilenceRequest(neuron_ids=neuron_ids)
        return await self._request(
            "POST", f"/v1/sessions/{session_id}/silence", SilenceResponse, request.model_dump(),
        )
