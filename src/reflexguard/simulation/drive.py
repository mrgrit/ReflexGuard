"""Differential drive and camera hand-off independent of Webots bindings."""
import math
from dataclasses import dataclass

WHEEL_RADIUS = 0.24
TRACK_WIDTH = 0.64


def wheel_speeds(forward: float, turn: float, max_speed: float) -> tuple[float, float]:
    """Positive turn is left; scale both wheels to preserve curvature."""
    if not all(math.isfinite(v) for v in (forward, turn, max_speed)) or not 0 < max_speed <= 1.2:
        raise ValueError("Invalid drive parameters")
    left = forward - turn * TRACK_WIDTH / 2
    right = forward + turn * TRACK_WIDTH / 2
    scale = max(1.0, abs(left) / max_speed, abs(right) / max_speed)
    return left / scale / WHEEL_RADIUS, right / scale / WHEEL_RADIUS


@dataclass(frozen=True)
class CameraFrame:
    t_ms: int
    width: int
    height: int
    bgra: bytes


class FrameSink:
    """Phase 3 encoder connection point; never retain a frame history."""
    def __init__(self):
        self.frames = 0
        self.pixel_range = 0

    def consume(self, frame: CameraFrame) -> None:
        if len(frame.bgra) != frame.width * frame.height * 4:
            raise ValueError("Incomplete camera frame")
        self.frames += 1
        # Exclude alpha: an opaque black frame is not evidence of rendering.
        channel = frame.bgra[0::4]
        self.pixel_range = max(self.pixel_range, max(channel) - min(channel))
