"""The rule-based implementation of the shared v1 brain API."""

import logging
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from reflexguard.common.config import MockSettings
from reflexguard.common.schemas import (
    CreateSessionRequest, HealthResponse, ID_PATTERN, SessionResponse,
    SilenceRequest, SilenceResponse, StepRequest, StepResponse,
)
from reflexguard.mock_brain.rules import MODEL_VERSION, RULES_SHA256
from reflexguard.mock_brain.security import BrainBoundary
from reflexguard.mock_brain.store import SessionStore

LOGGER = logging.getLogger(__name__)
SessionPath = Annotated[str, Path(min_length=1, max_length=128, pattern=ID_PATTERN)]


def create_app(settings: MockSettings | None = None) -> FastAPI:
    settings = settings if settings is not None else MockSettings.from_env()
    app = FastAPI(debug=False, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BrainBoundary, settings=settings)
    store = SessionStore(settings.max_sessions, settings.session_ttl_seconds)
    app.state.sessions = store

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        LOGGER.warning("Brain request validation failed: %d error(s)", len(exc.errors()))
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        messages = {
            403: "Permission denied", 404: "Resource unavailable", 405: "Method not allowed",
            409: "Request conflict", 422: "Invalid request", 503: "Service unavailable",
        }
        return JSONResponse(
            {"detail": messages.get(exc.status_code, "Request failed")}, status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        LOGGER.exception("Unhandled brain service error", exc_info=exc)
        return JSONResponse({"detail": "Service unavailable"}, status_code=500)

    @app.get("/v1/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(status="ok", model_version=MODEL_VERSION, weights_sha256=RULES_SHA256)

    @app.post("/v1/sessions", response_model=SessionResponse)
    async def create_session(
        request: Request, body: Annotated[CreateSessionRequest | None, Body()] = None,
    ):
        return SessionResponse(session_id=store.create(request.state.principal.subject))

    @app.post("/v1/sessions/{session_id}/step", response_model=StepResponse)
    async def step(session_id: SessionPath, body: StepRequest, request: Request):
        return store.step(session_id, request.state.principal.subject, body)

    @app.post("/v1/sessions/{session_id}/silence", response_model=SilenceResponse)
    async def silence(session_id: SessionPath, body: SilenceRequest, request: Request):
        principal = request.state.principal
        if principal.role not in ("operator", "admin"):
            raise HTTPException(status_code=403, detail="Permission denied")
        return store.silence(session_id, principal.subject, body)

    return app
