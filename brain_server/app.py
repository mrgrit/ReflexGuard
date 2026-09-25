"""The same authenticated v1 contract, backed by signed MaleCNS LIF assets."""
from contextlib import asynccontextmanager
import logging
from typing import Annotated
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from reflexguard.common.schemas import CreateSessionRequest, HealthResponse, SessionResponse, SilenceRequest, SilenceResponse, StepRequest, StepResponse
from reflexguard.mock_brain.app import SessionPath
from reflexguard.mock_brain.security import BrainBoundary
from brain_server.service import SimulationService

LOGGER = logging.getLogger(__name__)


def create_app(settings, circuit):
    service = SimulationService(circuit, settings.max_sessions, settings.session_ttl_seconds)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(debug=False, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(BrainBoundary, settings=settings)
    app.state.simulation = service

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def rejected(request, exc):
        return JSONResponse({"detail": "Request failed"}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def failed(request, exc):
        LOGGER.exception("Brain service error", exc_info=exc)
        return JSONResponse({"detail": "Service unavailable"}, status_code=500)

    @app.get('/v1/health', response_model=HealthResponse)
    async def health():
        if service.failed:
            raise HTTPException(503)
        return HealthResponse(status="ok", model_version=circuit.manifest.model_version, weights_sha256=circuit.manifest.weights_sha256)

    @app.post('/v1/sessions', response_model=SessionResponse)
    async def create(request: Request, body: Annotated[CreateSessionRequest | None, Body()] = None):
        return SessionResponse(session_id=service.create(request.state.principal.subject))

    @app.post('/v1/sessions/{session_id}/step', response_model=StepResponse)
    async def step(session_id: SessionPath, body: StepRequest, request: Request):
        return await service.step(session_id, request.state.principal.subject, body)

    @app.post('/v1/sessions/{session_id}/silence', response_model=SilenceResponse)
    async def silence(session_id: SessionPath, body: SilenceRequest, request: Request):
        principal = request.state.principal
        if principal.role not in ('operator', 'admin'):
            raise HTTPException(403)
        return service.silence(session_id, principal.subject, body)

    return app
