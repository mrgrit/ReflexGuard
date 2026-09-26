"""Validated fixed-path calibration, never credentials or user file paths."""
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)
    drive_speed: float = Field(default=2.0, gt=0, le=3.0)
    dark_threshold: int = Field(default=140, ge=1, le=254)
    area_floor: float = Field(default=0.008, gt=0, le=0.1)
    area_tau_s: float = Field(default=0.12, gt=0, le=1)
    looming_tau_s: float = Field(default=0.15, gt=0, le=1)
    expansion_scale: float = Field(default=1.0, gt=0, le=10)
    stop_on: float = Field(default=0.3, gt=0, le=1)
    stop_off: float = Field(default=0.12, ge=0, lt=1)
    turn_on: float = Field(default=0.25, gt=0, le=1)
    turn_off: float = Field(default=0.10, ge=0, lt=1)
    turn_gain: float = Field(default=0.5, ge=0, le=1)
    max_turn: float = Field(default=1.2, gt=0, le=2)
    deceleration: float = Field(default=2.0, gt=0, le=5)
    release_ms: int = Field(default=500, ge=100, le=3000)

    @model_validator(mode="after")
    def hysteresis_order(self):
        if self.stop_off >= self.stop_on or self.turn_off >= self.turn_on:
            raise ValueError("Release thresholds must be below activation thresholds")
        return self

    @classmethod
    def load(cls):
        from reflexguard.control.settings_store import CalibrationStore
        return CalibrationStore().snapshot().calibration
