"""Validated scenario inputs and observable simulation results."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

World = Literal["corridor_basic", "corridor_side", "corridor_static"]
Drive = Literal["keyboard", "idle", "forward", "reverse", "left", "right"]

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    world: World = "corridor_basic"
    duration_s: int = Field(default=10, ge=1, le=60)
    drive: Drive = "keyboard"
    batch: bool = False

class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    frames: int = Field(ge=0)
    width: int = Field(ge=160, le=640)
    height: int = Field(ge=120, le=480)
    pixel_range: int = Field(ge=0, le=255)
    left_rad_s: float = Field(allow_inf_nan=False)
    right_rad_s: float = Field(allow_inf_nan=False)

    brain_steps: int = Field(default=0, ge=0)
    interventions: int = Field(default=0, ge=0)
    stop_steps: int = Field(default=0, ge=0)
    brain_failures: int = Field(default=0, ge=0)
    max_looming: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    final_forward: float = Field(default=0.0, ge=-1.2, le=1.2, allow_inf_nan=False)

class Result(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    world: World
    drive: Drive
    duration_s: float = Field(gt=0, le=61, allow_inf_nan=False)
    collision: bool
    collision_events: int = Field(ge=0)
    min_clearance_estimate_m: float = Field(ge=0, allow_inf_nan=False)
    displacement_m: float = Field(ge=0, allow_inf_nan=False)
    yaw_change_rad: float = Field(allow_inf_nan=False)
    camera_frames: int = Field(gt=0)
    camera_pixel_range: int = Field(gt=0, le=255)
    camera_width: int = Field(ge=160)
    camera_height: int = Field(ge=120)

    brain_steps: int = Field(default=0, ge=0)
    interventions: int = Field(default=0, ge=0)
    stop_steps: int = Field(default=0, ge=0)
    brain_failures: int = Field(default=0, ge=0)
    max_looming: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    final_forward: float = Field(default=0.0, ge=-1.2, le=1.2, allow_inf_nan=False)
