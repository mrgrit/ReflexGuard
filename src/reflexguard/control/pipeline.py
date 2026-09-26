"""Camera → mTLS brain → decoder → arbiter; never consume simulator positions."""
import logging
from dataclasses import dataclass
from reflexguard.brain_client.client import BrainClient, BrainClientError
from reflexguard.common.config import ConfigurationError
from reflexguard.common.schemas import StepRequest
from reflexguard.control.avoidance import LocalAvoidance, Surroundings
from reflexguard.control.arbiter import Arbiter, Command, Decision
from reflexguard.control.config import Calibration
from reflexguard.decoder.decoder import Decoder, Signal
from reflexguard.encoder.looming import LoomingEncoder, Looming
from reflexguard.simulation.drive import CameraFrame

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineStep:
    decision: Decision
    looming: Looming
    escape: float
    signal: Signal


class Pipeline:
    def __init__(self, config: Calibration, client=None, avoidance=False):
        self.navigator = LocalAvoidance(config) if avoidance else None
        self.encoder = LoomingEncoder(config)
        self.decoder = Decoder(config)
        self.arbiter = Arbiter(config)
        self.client = client
        self.session_id = None
        self.failed = False
        self.navigation_steps = 0
        self.recoveries = 0
        self.brain_steps = 0
        self.interventions = 0
        self.stop_steps = 0
        self.failures = 0
        self.last = Looming(0.0, 0.0, 0.0, 0.0)
        self.top_neurons = []
        self.neuron_activity = []
        self.weights_sha256 = ""
        self.model_version = "unavailable"

    async def start(self):
        try:
            if self.client is None:
                self.client = BrainClient()
            health = await self.client.health()
            self.weights_sha256 = health.weights_sha256
            self.session_id = (await self.client.create_session()).session_id
        except (BrainClientError, ConfigurationError):
            self.fail()

    def fail(self):
        if not self.failed:
            LOGGER.warning("Safety stop latched; restart required after correcting the fault")
            self.failures += 1
        self.failed = True
        self.top_neurons = []
        self.neuron_activity = []
        self.weights_sha256 = ""
        self.model_version = "unavailable"

    async def step(self, frame: CameraFrame | None, user: Command, dt_ms: int, surroundings: Surroundings | None = None) -> PipelineStep:
        escape = 0.0
        signal = Signal.NONE
        if not self.failed:
            try:
                if frame is None:
                    raise ValueError("Camera frame missing")
                self.last = self.encoder.update(frame)
                response = await self.client.step(self.session_id, StepRequest(
                    t_ms=frame.t_ms, dt_ms=dt_ms, left_looming=self.last.left, right_looming=self.last.right))
                signal = self.decoder.update(response)
                escape = response.escape
                self.top_neurons = response.top_neurons
                if response.neuron_activity:
                    self.neuron_activity = response.neuron_activity
                self.model_version = response.model_version
                self.brain_steps += 1
            except (BrainClientError, ValueError):
                self.fail()
        if self.navigator is not None:
            decision = self.navigator.update(user, signal, escape, dt_ms, not self.failed, surroundings,
                                             frame.t_ms if frame is not None else -1)
        else:
            decision = self.arbiter.update(user, signal, escape, dt_ms, healthy=not self.failed)
        self.navigation_steps += int(decision.reason.startswith("avoid_") or decision.reason == "control_recovering")
        self.recoveries += int(decision.reason == "control_recovered")
        self.interventions += int(decision.intervened)
        self.stop_steps += int(decision.reason in ("hazard_stop", "brain_failure", "sensor_failure", "path_blocked"))
        return PipelineStep(decision, self.last, escape, signal)

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
