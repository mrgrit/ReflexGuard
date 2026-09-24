"""Bounded session state; ownership and expiry are enforced on every operation."""

from dataclasses import dataclass, field
import secrets
from threading import Lock
import time

from fastapi import HTTPException

from reflexguard.common.schemas import SilenceRequest, SilenceResponse, StepRequest
from reflexguard.mock_brain.rules import NEURON_IDS, evaluate


@dataclass
class Session:
    owner: str
    touched: float
    last_t_ms: int = -1
    silenced: set[str] = field(default_factory=set)


class SessionStore:
    def __init__(self, max_sessions: int, ttl_seconds: int, clock=time.monotonic):
        self._sessions: dict[str, Session] = {}
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = Lock()

    def _expire(self, now):
        expired = [key for key, state in self._sessions.items()
                   if now - state.touched >= self._ttl]
        for key in expired:
            del self._sessions[key]

    def create(self, owner):
        with self._lock:
            now = self._clock()
            self._expire(now)
            if len(self._sessions) >= self._max_sessions:
                raise HTTPException(status_code=503, detail="Service unavailable")
            session_id = secrets.token_urlsafe(24)
            while session_id in self._sessions:
                session_id = secrets.token_urlsafe(24)
            self._sessions[session_id] = Session(owner=owner, touched=now)
            return session_id

    def _owned(self, session_id, owner):
        now = self._clock()
        self._expire(now)
        state = self._sessions.get(session_id)
        if state is None or state.owner != owner:
            raise HTTPException(status_code=404, detail="Resource unavailable")
        return state, now

    def step(self, session_id, owner, request: StepRequest):
        with self._lock:
            state, now = self._owned(session_id, owner)
            if request.t_ms <= state.last_t_ms:
                raise HTTPException(status_code=409, detail="Request conflict")
            response = evaluate(request, state.silenced)
            state.last_t_ms = request.t_ms
            state.touched = now
            return response

    def silence(self, session_id, owner, request: SilenceRequest):
        with self._lock:
            state, now = self._owned(session_id, owner)
            if not set(request.neuron_ids).issubset(NEURON_IDS):
                raise HTTPException(status_code=422, detail="Invalid request")
            # Replaces the entire set; [] clears it. Never accumulate beyond ten.
            state.silenced = set(request.neuron_ids)
            state.touched = now
            return SilenceResponse(accepted=request.neuron_ids)
