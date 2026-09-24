"""Shared control from camera pixels and authenticated brain responses."""
import asyncio
import json
import os
from pathlib import Path
from typing import Annotated
from controller import Robot, Keyboard
from pydantic import TypeAdapter, Field
from reflexguard.control.arbiter import Command
from reflexguard.control.config import Calibration
from reflexguard.control.pipeline import Pipeline
from reflexguard.control_server.device_client import DeviceClient, DeviceSettings
from reflexguard.simulation.drive import CameraFrame, FrameSink, wheel_speeds
from reflexguard.simulation.models import Settings, Telemetry


async def main():
    robot = Robot()
    os.chdir(Path(__file__).resolve().parents[3])
    dt = int(robot.getBasicTimeStep())
    settings = Settings.model_validate_json(os.environ.get("REFLEXGUARD_SCENARIO", "{}"))
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
    pipeline = Pipeline(Calibration.load())
    device = DeviceClient(DeviceSettings.from_env()) if os.environ.get("REFLEXGUARD_CONTROL_URL") else None
    presets = {"idle": (0.0, 0.0), "forward": (max_speed, 0.0),
               "reverse": (-max_speed, 0.0), "left": (0.0, 0.8), "right": (0.0, -0.8)}
    maximum = 0.0
    remote_stops = 0
    remote_interventions = 0
    last_reason = None
    next_log_ms = 0
    try:
        await pipeline.start()
        if device is not None:
            await device.start()
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
            raw = camera.getImage()
            now_ms = round(robot.getTime() * 1000)
            frame = None if raw is None else CameraFrame(now_ms, camera.getWidth(), camera.getHeight(), bytes(raw))
            if frame is not None:
                sink.consume(frame)
            result = await pipeline.step(frame, Command(forward=forward, turn=turn), dt)
            command = result.decision.command
            reason = result.decision.reason
            if device is not None:
                await device.poll(pipeline)
                command = device.guard.apply(command)
                if device.guard.stopped:
                    reason = "control_failure" if device.failed else "remote_stop"
                elif command != result.decision.command:
                    reason = "remote_speed_limit"
            remote_stops += int(device is not None and device.guard.stopped)
            remote_interventions += int(command != result.decision.command)
            lv, rv = wheel_speeds(command.forward, command.turn, max_speed)
            left.setVelocity(lv)
            right.setVelocity(rv)
            maximum = max(maximum, result.looming.left, result.looming.right)
            robot.setCustomData(Telemetry(
                frames=sink.frames, width=camera.getWidth(), height=camera.getHeight(),
                pixel_range=sink.pixel_range, left_rad_s=lv, right_rad_s=rv,
                remote_stop_steps=remote_stops, remote_interventions=remote_interventions,
                control_failures=int(device is not None and device.failed), brain_steps=pipeline.brain_steps, interventions=pipeline.interventions,
                stop_steps=pipeline.stop_steps, brain_failures=pipeline.failures,
                max_looming=maximum, final_forward=command.forward).model_dump_json())
            if now_ms >= next_log_ms or reason != last_reason:
                if device is not None:
                    await device.report(t_ms=now_ms, result=result, command=command, reason=reason,
                                        top_neurons=pipeline.top_neurons, model_version=pipeline.model_version)
                    if device.failed:
                        left.setVelocity(0.0)
                        right.setVelocity(0.0)
                print("REFLEXGUARD_DECISION=" + json.dumps({
                    "t_ms": now_ms, "left": result.looming.left, "right": result.looming.right,
                    "left_area": result.looming.left_area, "right_area": result.looming.right_area,
                    "escape": result.escape, "signal": result.signal.value,
                    "reason": reason, "user_forward": forward, "forward": command.forward,
                    "turn": command.turn, "intervened": command != Command(forward=forward, turn=turn)}), flush=True)
                next_log_ms = now_ms + 500
                last_reason = reason
    finally:
        left.setVelocity(0.0)
        right.setVelocity(0.0)
        await pipeline.close()
        if device is not None:
            await device.close()


if __name__ == "__main__":
    asyncio.run(main())
