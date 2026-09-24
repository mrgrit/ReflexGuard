"""Keyboard-controlled simulated wheelchair; camera ready for Phase 3."""
import os
from controller import Robot, Keyboard
from reflexguard.simulation.drive import CameraFrame, FrameSink, wheel_speeds
from reflexguard.simulation.models import Settings, Telemetry
from pydantic import TypeAdapter, Field
from typing import Annotated


def main():
    robot = Robot()
    dt = int(robot.getBasicTimeStep())
    settings = Settings.model_validate_json(os.environ.get("REFLEXGUARD_SCENARIO", "{}"))
    # PROTO passes its speed limit through Robot.customData.
    max_speed = TypeAdapter(Annotated[float, Field(gt=0, le=1.2)]).validate_json(robot.getCustomData())
    left = robot.getDevice("left wheel motor")
    right = robot.getDevice("right wheel motor")
    for motor in (left, right):
        motor.setPosition(float("inf"))
        motor.setVelocity(0.0)
    camera = robot.getDevice("front camera")
    camera.enable(dt)
    keyboard = robot.getKeyboard()
    keyboard.enable(dt)
    sink = FrameSink()
    presets = {"idle": (0.0, 0.0), "forward": (max_speed, 0.0),
               "reverse": (-max_speed, 0.0), "left": (0.0, 0.8), "right": (0.0, -0.8)}
    print("REFLEXGUARD: camera and wheel controller ready", flush=True)
    try:
        while robot.step(dt) != -1:
            if settings.drive == "keyboard":
                keys = set()
                key = keyboard.getKey()
                while key != -1:
                    keys.add(key)
                    key = keyboard.getKey()
                forward = max_speed * (int(Keyboard.UP in keys) - int(Keyboard.DOWN in keys))
                turn = 0.8 * (int(Keyboard.LEFT in keys) - int(Keyboard.RIGHT in keys))
                if ord(" ") in keys:
                    forward = turn = 0.0
            else:
                forward, turn = presets[settings.drive]
            lv, rv = wheel_speeds(forward, turn, max_speed)
            left.setVelocity(lv)
            right.setVelocity(rv)
            raw = camera.getImage()
            if raw is not None:
                sink.consume(CameraFrame(round(robot.getTime() * 1000), camera.getWidth(), camera.getHeight(), bytes(raw)))
            robot.setCustomData(Telemetry(frames=sink.frames, width=camera.getWidth(), height=camera.getHeight(),
                                         pixel_range=sink.pixel_range, left_rad_s=lv, right_rad_s=rv).model_dump_json())
    finally:
        left.setVelocity(0.0)
        right.setVelocity(0.0)


if __name__ == "__main__":
    main()
