"""Shared control from camera pixels and authenticated brain responses."""
import asyncio
import json
import math
import os
import time
from pathlib import Path
from typing import Annotated
from controller import Robot, Keyboard
from pydantic import TypeAdapter, Field
from reflexguard.control.arbiter import Command
from reflexguard.control.avoidance import Surroundings
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
    max_speed = TypeAdapter(Annotated[float, Field(gt=0, le=3.0)]).validate_json(robot.getCustomData())
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
    calibration = Calibration.load()
    print("REFLEXGUARD_CALIBRATION=" + calibration.model_dump_json(), flush=True)
    max_speed = min(max_speed, calibration.drive_speed)
    devices = {robot.getDeviceByIndex(i).getName(): robot.getDeviceByIndex(i) for i in range(robot.getNumberOfDevices())}
    heading = devices.get("avoidance heading")
    range_devices = [devices.get("range " + name) for name in ("front", "left", "rear", "right")]
    upper_devices = [devices.get("range upper " + name) for name in ("front", "left", "rear", "right")]
    rear_camera = devices.get("rear camera")
    if rear_camera is not None and not settings.batch:
        rear_camera.enable(128)
    avoidance = heading is not None
    encoders = [devices.get(name + " wheel position") for name in ("left", "right")]
    last_wheel_distance = None
    last_heading = None
    if avoidance:
        if any(device is None for device in encoders):
            raise ValueError("Wheel odometry missing")
        for encoder in encoders:
            encoder.enable(dt)
        if any(device is None for device in range_devices + upper_devices):
            raise ValueError("Incomplete range sensor set")
        heading.enable(dt)
        for sensor in range_devices + upper_devices:
            sensor.enable(dt)
    pipeline = Pipeline(calibration, avoidance=avoidance)
    device = DeviceClient(DeviceSettings.from_env(), max_speed=max_speed) if os.environ.get("REFLEXGUARD_CONTROL_URL") else None
    presets = {"idle": (0.0, 0.0), "forward": (max_speed, 0.0),
               "reverse": (-max_speed, 0.0), "left": (0.0, 0.8), "right": (0.0, -0.8)}
    maximum = 0.0
    remote_stops = 0
    remote_interventions = 0
    last_reason = None
    next_log_ms = 0
    next_poll_at = 0.0
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
            surroundings = None
            if avoidance:
                try:
                    wheel_distance = sum(encoder.getValue() for encoder in encoders) * .12
                    travel = 0.0 if last_wheel_distance is None else wheel_distance - last_wheel_distance
                    last_wheel_distance = wheel_distance
                    yaw = heading.getRollPitchYaw()[2]
                    rotation = 0.0 if last_heading is None else math.atan2(math.sin(yaw-last_heading), math.cos(yaw-last_heading)) * 1000 / dt
                    last_heading = yaw
                    surroundings = Surroundings.from_heights(
                        [sensor.getRangeImage() for sensor in range_devices],
                        [sensor.getRangeImage() for sensor in upper_devices],
                        t_ms=now_ms, travel_m=travel, forward_mps=travel * 1000 / dt,
                        turn_rad_s=rotation, heading=yaw)
                except ValueError:
                    surroundings = None  # Either faulty height latches a stop in the pipeline.
            if surroundings is not None and sink.frames == 1:
                print("REFLEXGUARD_RANGES=" + json.dumps({"heading": surroundings.heading,
                    "nearest": [min(row) for row in surroundings.ranges]}), flush=True)
            result = await pipeline.step(frame, Command(forward=forward, turn=turn), dt, surroundings)
            command = result.decision.command
            reason = result.decision.reason
            if device is not None:
                if time.monotonic() >= next_poll_at:
                    await device.poll(pipeline)
                    next_poll_at = time.monotonic() + .1
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
                model_version=pipeline.model_version, escape=result.escape,
                reason=reason, requested_forward=forward,
                frames=sink.frames, width=camera.getWidth(), height=camera.getHeight(),
                pixel_range=sink.pixel_range, left_rad_s=lv, right_rad_s=rv,
                remote_stop_steps=remote_stops, remote_interventions=remote_interventions,
                control_failures=int(device is not None and device.failed), brain_steps=pipeline.brain_steps, interventions=pipeline.interventions,
                navigation_steps=pipeline.navigation_steps, recoveries=pipeline.recoveries,
                stop_steps=pipeline.stop_steps, brain_failures=pipeline.failures,
                max_looming=maximum, final_forward=command.forward).model_dump_json())
            urgent = reason in ("brain_failure", "sensor_failure", "control_failure", "remote_stop", "hazard_stop")
            if now_ms >= next_log_ms or urgent and reason != last_reason:
                if device is not None:
                    await device.report(t_ms=now_ms, result=result, command=command, reason=reason,
                                        top_neurons=pipeline.top_neurons, model_version=pipeline.model_version,
                                        navigation_mode="range_assisted" if avoidance else "reflex_stop",
                                        neuron_activity=pipeline.neuron_activity, weights_sha256=pipeline.weights_sha256)
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
