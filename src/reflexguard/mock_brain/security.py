"""Authentication and bounded request ingestion for every HTTP endpoint."""

import asyncio
from dataclasses import dataclass
import secrets
from typing import Annotated

from pydantic import StringConstraints, TypeAdapter, ValidationError
from starlette.responses import JSONResponse

from reflexguard.common.config import BEARER_PATTERN, MockSettings, Role

MAX_REQUEST_BYTES = 16 * 1024
BODY_TIMEOUT_SECONDS = 1.0
TOKEN = TypeAdapter(Annotated[str, StringConstraints(pattern=BEARER_PATTERN)])


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role


class BodyTooLarge(Exception):
    """Request size exceeded its fixed limit."""


class BrainBoundary:
    """mTLS is enforced by the launcher; forwarded headers are never trusted."""

    def __init__(self, app, settings: MockSettings):
        self.app = app
        self.records = settings.tokens

    def _authenticate(self, scope):
        headers = [value for key, value in scope.get("headers", [])
                   if key.lower() == b"authorization"]
        if len(headers) != 1:
            return None
        try:
            scheme, value = headers[0].decode("ascii").split(" ", 1)
            if scheme.lower() != "bearer":
                return None
            token = TOKEN.validate_python(value)
        except (UnicodeError, ValueError, ValidationError):
            return None
        principal = None
        for record in self.records:
            if secrets.compare_digest(token, record.token.get_secret_value()):
                principal = Principal(subject=record.subject, role=record.role)
        return principal

    @staticmethod
    async def _body(receive):
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            body.extend(message.get("body", b""))
            if len(body) > MAX_REQUEST_BYTES:
                raise BodyTooLarge
            if not message.get("more_body", False):
                return bytes(body)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("scheme") != "https":
            await JSONResponse({"detail": "HTTPS required"}, status_code=400)(scope, receive, send)
            return
        principal = self._authenticate(scope)
        if principal is None:
            await JSONResponse(
                {"detail": "Authentication required"}, status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )(scope, receive, send)
            return
        try:
            body = await asyncio.wait_for(self._body(receive), BODY_TIMEOUT_SECONDS)
        except BodyTooLarge:
            await JSONResponse({"detail": "Request too large"}, status_code=413)(scope, receive, send)
            return
        except asyncio.TimeoutError:
            await JSONResponse({"detail": "Request timeout"}, status_code=408)(scope, receive, send)
            return
        if body is None:
            return
        scope.setdefault("state", {})["principal"] = principal
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        await self.app(scope, bounded_receive, secure_send)
