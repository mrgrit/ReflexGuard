"""Shared control with neutral-input rearming and latched failure stops."""
from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from typing import Annotated
from reflexguard.control.config import Calibration
from reflexguard.decoder.decoder import Signal

DT = TypeAdapter(Annotated[int, Field(strict=True, ge=1, le=100)])
ESCAPE = TypeAdapter(Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)])


class Command(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always")
    forward: float = Field(ge=-6.0, le=6.0)
    turn: float = Field(ge=-2, le=2)


@dataclass(frozen=True)
class Decision:
    command: Command
    reason: str
    intervened: bool


def approach_zero(value: float, amount: float) -> float:
    if value > 0:
        return max(0.0, value - amount)
    return min(0.0, value + amount)


class Arbiter:
    def __init__(self, config: Calibration):
        self.config = config
        self.previous = Command(forward=0.0, turn=0.0)
        self.stopped = False
        self.fault = False
        self.neutral_ms = 0

    def update(self, user: Command, signal: Signal, escape: float, dt_ms: int, healthy: bool = True) -> Decision:
        user = Command.model_validate(user)
        dt_ms = DT.validate_python(dt_ms)
        escape = ESCAPE.validate_python(escape)
        signal = Signal(signal)
        active = user.forward != 0 or user.turn != 0
        self.fault = self.fault or not healthy
        if active and (signal == Signal.STOP or escape >= self.config.stop_on):
            self.stopped = True
        if not active and signal == Signal.NONE and not self.fault:
            self.neutral_ms += dt_ms
            if self.neutral_ms >= self.config.release_ms:
                self.stopped = False
        else:
            self.neutral_ms = 0
        reason = "user"
        if self.fault or self.stopped:
            reason = "brain_failure" if self.fault else "hazard_stop"
            command = Command(forward=approach_zero(self.previous.forward, self.config.deceleration * dt_ms / 1000),
                              turn=approach_zero(self.previous.turn, self.config.deceleration * 2 * dt_ms / 1000))
        elif not active:
            command = user
            reason = "idle"
        elif signal in (Signal.LEFT, Signal.RIGHT):
            offset = self.config.turn_gain * (1 if signal == Signal.LEFT else -1)
            command = Command(forward=user.forward,
                              turn=max(-self.config.max_turn, min(self.config.max_turn, user.turn + offset)))
            reason = "avoid_turn"
        else:
            command = user
        intervened = command != user
        self.previous = command
        return Decision(command, reason, intervened)
