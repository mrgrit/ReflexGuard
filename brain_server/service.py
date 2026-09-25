"""Bounded admission, owner isolation and transactional per-session LIF state."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import logging
import secrets
import time
from fastapi import HTTPException

from reflexguard.common.schemas import SilenceResponse

LOGGER = logging.getLogger(__name__)


@dataclass
class Session:
    owner: str
    state: object
    touched: float
    last_t_ms: int = -1
    silenced: set[str] = field(default_factory=set)
    busy: bool = False


class SimulationService:
    def __init__(self, circuit, max_sessions=16, ttl=900):
        self.circuit = circuit
        self.max_sessions = min(max_sessions, 16)
        self.ttl = ttl
        self.sessions = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lif")
        self.gate = asyncio.Semaphore(1)
        self.pending = 0
        self.failed = False

    def close(self):
        self.failed = True
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _expire(self):
        now = time.monotonic()
        for key in list(self.sessions):
            state = self.sessions[key]
            if not state.busy and now - state.touched >= self.ttl:
                del self.sessions[key]

    def create(self, owner):
        self._expire()
        if self.failed or len(self.sessions) >= self.max_sessions:
            raise HTTPException(503)
        key = secrets.token_urlsafe(24)
        self.sessions[key] = Session(owner, self.circuit.state(), time.monotonic())
        return key

    def owned(self, key, owner):
        self._expire()
        state = self.sessions.get(key)
        if state is None or state.owner != owner:
            raise HTTPException(404)
        if state.busy:
            raise HTTPException(409)
        return state

    def silence(self, key, owner, request):
        state = self.owned(key, owner)
        if not set(request.neuron_ids) <= self.circuit.allowed:
            raise HTTPException(422)
        state.silenced = set(request.neuron_ids)
        state.touched = time.monotonic()
        return SilenceResponse(accepted=request.neuron_ids)

    async def step(self, key, owner, request):
        state = self.owned(key, owner)
        if self.failed or self.pending >= 4:
            raise HTTPException(503)
        if request.t_ms <= state.last_t_ms:
            raise HTTPException(409)
        state.busy = True
        self.pending += 1
        acquired = False
        future = None
        deadline = time.monotonic() + 0.150
        try:
            try:
                await asyncio.wait_for(self.gate.acquire(), timeout=0.020)
            except asyncio.TimeoutError:
                raise HTTPException(503) from None
            acquired = True
            if self.failed:
                raise HTTPException(503)
            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(self.executor, self.circuit.step, state.state, request, state.silenced.copy(), deadline)
            # shield leaves the sole worker alive and bounded if a caller disconnects.
            updated, response = await asyncio.wait_for(asyncio.shield(future), max(0.001, deadline - time.monotonic()))
            if time.monotonic() >= deadline:
                raise TimeoutError("Response deadline exceeded")
            state.state = updated
            state.last_t_ms = request.t_ms
            state.touched = time.monotonic()
            return response
        except HTTPException:
            raise
        except (Exception, asyncio.CancelledError) as exc:
            # Uncertain GPU state disables all new simulation work until restart.
            self.failed = True
            self.sessions.pop(key, None)
            LOGGER.error("Simulation failed; restart required (%s)", type(exc).__name__)
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise HTTPException(503) from None
        finally:
            self.pending -= 1
            state.busy = False
            if acquired:
                if future is not None and not future.done():
                    def release(completed):
                        # Consume worker errors without leaking request/state details.
                        if not completed.cancelled():
                            completed.exception()
                        self.gate.release()
                    future.add_done_callback(release)
                else:
                    self.gate.release()
