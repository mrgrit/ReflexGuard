"""Dark-area relative expansion with time-scaled exponential smoothing."""
import math
from dataclasses import dataclass
import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from reflexguard.control.config import Calibration
from reflexguard.simulation.drive import CameraFrame


class FrameMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    t_ms: int = Field(ge=0)
    width: int = Field(ge=160, le=640, multiple_of=2)
    height: int = Field(ge=120, le=480)


@dataclass(frozen=True)
class Looming:
    left: float
    right: float
    left_area: float
    right_area: float


class LoomingEncoder:
    def __init__(self, config: Calibration):
        self.config = config
        self.time_ms = None
        self.shape = None
        self.area = None
        self.value = np.zeros(2, dtype=np.float64)

    def update(self, frame: CameraFrame) -> Looming:
        FrameMetadata(t_ms=frame.t_ms, width=frame.width, height=frame.height)
        if not isinstance(frame.bgra, bytes) or len(frame.bgra) != frame.width * frame.height * 4:
            raise ValueError("Invalid camera buffer")
        shape = (frame.height, frame.width)
        if self.shape is not None and self.shape != shape:
            raise ValueError("Camera resolution changed")
        if self.time_ms is not None and not 1 <= frame.t_ms - self.time_ms <= 100:
            raise ValueError("Stale or discontinuous camera frame")
        gray = cv2.cvtColor(np.frombuffer(frame.bgra, np.uint8).reshape(*shape, 4), cv2.COLOR_BGRA2GRAY)
        # Exclude ceiling and near-floor border; the forward scene fills the rest.
        gray = gray[frame.height // 10:frame.height * 9 // 10]
        mask = (gray < self.config.dark_threshold).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mid = frame.width // 2
        area = np.array([mask[:, :mid].mean(), mask[:, mid:].mean()])
        if self.time_ms is None:
            self.area = area
        else:
            seconds = (frame.t_ms - self.time_ms) / 1000
            area_alpha = -math.expm1(-seconds / self.config.area_tau_s)
            new_area = self.area + area_alpha * (area - self.area)
            growth = np.maximum(0, new_area - self.area) / (np.maximum(self.area, self.config.area_floor) * seconds)
            target = np.clip(growth / self.config.expansion_scale, 0, 1)
            alpha = -math.expm1(-seconds / self.config.looming_tau_s)
            self.value += alpha * (target - self.value)
            self.area = new_area
        self.time_ms = frame.t_ms
        self.shape = shape
        return Looming(float(self.value[0]), float(self.value[1]), float(area[0]), float(area[1]))
