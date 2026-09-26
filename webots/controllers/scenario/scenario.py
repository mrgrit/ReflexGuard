"""Observe contacts and finish bounded batch runs without controlling motors."""
import math
import os
import json
from controller import Supervisor
from reflexguard.simulation.models import Settings, Telemetry, Result
from reflexguard.simulation.geometry import box_clearance, circle_clearance, PEDESTRIAN_RADIUS, has_hazard_contact



def main():
    sim = Supervisor()
    dt = int(sim.getBasicTimeStep())
    world = sim.getSelf().getField("customData").getSFString()
    raw = os.environ.get("REFLEXGUARD_SCENARIO")
    settings = Settings.model_validate_json(raw) if raw else Settings(world=world)
    if settings.world != world:
        raise ValueError("Scenario world mismatch")
    chair = sim.getFromDef("CHAIR")
    obstacle = sim.getFromDef("OBSTACLE")
    hazards = [obstacle] + [sim.getFromDef(name) for name in
                            ("WALL_SOUTH", "WALL_NW", "WALL_NE", "WALL_WEST", "WALL_EAST")]
    walls = []
    for wall in hazards[1:]:
        wx, wy, _ = wall.getPosition()
        box = wall.getField("boundingObject").getSFNode()
        sx, sy, _ = box.getField("size").getSFVec3f()
        walls.append((wx, wy, sx / 2, sy / 2))
    extra_boxes = [sim.getFromDef(name) for name in ("BOX_A", "BOX_B", "BOX_C", "GATE_N", "GATE_S")]
    extra_boxes = [node for node in extra_boxes if node is not None]
    extra_people = [sim.getFromDef("PERSON_B")]
    extra_people = [node for node in extra_people if node is not None]
    people = [obstacle] + extra_people if world == "corridor_demo" else []
    last_positions = [person.getPosition() for person in people]
    pedestrian_travel = [0.0 for person in people]
    hazards.extend(extra_boxes + extra_people)
    if not settings.batch:
        for i in range(sim.getNumberOfDevices()):
            camera = sim.getDeviceByIndex(i)
            camera.enable(128)
    start = chair.getPosition()
    initial_orientation = chair.getOrientation()
    initial_yaw = math.atan2(initial_orientation[3], initial_orientation[0])
    minimum = 100.0
    events = 0
    previous_contact = False
    next_label = 0.0
    while sim.step(dt) != -1:
        for index, person in enumerate(people):
            position = person.getPosition()
            pedestrian_travel[index] += math.hypot(position[0] - last_positions[index][0], position[1] - last_positions[index][1])
            last_positions[index] = position
        x, y, _ = chair.getPosition()
        ox, oy, _ = obstacle.getPosition()
        distances = [box_clearance(x, y, *wall) for wall in walls]
        if world == "corridor_static":
            distances.append(box_clearance(x, y, ox, oy, 0.3, 0.4))
        else:
            distances.append(circle_clearance(x, y, ox, oy, PEDESTRIAN_RADIUS))
        for box in extra_boxes:
            bx, by, _ = box.getPosition()
            sx, sy, _ = box.getField("boundingObject").getSFNode().getField("size").getSFVec3f()
            distances.append(box_clearance(x, y, bx, by, sx / 2, sy / 2))
        for person in extra_people:
            px, py, _ = person.getPosition()
            distances.append(circle_clearance(x, y, px, py, PEDESTRIAN_RADIUS))
        minimum = min(minimum, *distances)
        contact = has_hazard_contact(
            [point.point for point in chair.getContactPoints(True)],
            [point.point for hazard in hazards for point in hazard.getContactPoints(True)],
        )
        if contact and not previous_contact:
            events += 1
            touched = [hazard.getDef() or hazard.getField("name").getSFString() for hazard in hazards
                       if has_hazard_contact([point.point for point in chair.getContactPoints(True)],
                                             [point.point for point in hazard.getContactPoints(True)])]
            print("REFLEXGUARD_CONTACT=" + json.dumps({"t_ms": round(sim.getTime() * 1000), "x": x, "y": y, "hazards": touched}), flush=True)
        previous_contact = contact
        if not settings.batch and sim.getTime() >= next_label:
            raw_status = chair.getBaseNodeField("customData").getSFString()
            try:
                status = Telemetry.model_validate_json(raw_status)
            except ValueError:
                status = None
            if status is not None:
                label = status.reason.replace("_", " ").upper()
                color = 0xC02020 if status.reason.endswith("failure") or status.reason in ("path_blocked", "remote_stop") else 0xD07000 if status.reason.startswith("avoid") else 0x126090
                sim.setLabel(0, f"{label} | {status.final_forward:.2f} m/s | CONTACTS {events}", .02, .02, .05, color)
                sim.setLabel(1, f"REQUEST {status.requested_forward:.2f} m/s | BRAIN + LOCAL RANGE ASSIST" if world == "corridor_demo" else f"REQUEST {status.requested_forward:.2f} m/s | REFLEX STOP", .02, .08, .035, 0x142B38)
                backend = "LOCAL CPU" if os.environ.get("REFLEXGUARD_BRAIN_PROFILE") == "local" else "REMOTE GPU"
                model = "MaleCNS v1.0 / 187 neurons / " + backend if status.model_version == "malecns-v1.0-lplc2-gf-lif-v1" else "MOCK / virtual neurons" if status.model_version.startswith("mock-") else "BRAIN UNAVAILABLE"
                sim.setLabel(2, f"{model} | ESCAPE {status.escape:.3f}", .02, .13, .035, 0x142B38)
            next_label = sim.getTime() + .128
        if settings.batch and sim.getTime() >= settings.duration_s:
            telemetry = Telemetry.model_validate_json(chair.getBaseNodeField("customData").getSFString())
            orientation = chair.getOrientation()
            yaw = math.atan2(orientation[3], orientation[0]) - initial_yaw
            result = Result(world=world, drive=settings.drive, duration_s=sim.getTime(),
                            min_pedestrian_travel_m=min(pedestrian_travel, default=0.0),
                            collision=events > 0, collision_events=events,
                            min_clearance_estimate_m=minimum, displacement_m=math.hypot(x-start[0], y-start[1]),
                            yaw_change_rad=math.atan2(math.sin(yaw), math.cos(yaw)),
                            camera_frames=telemetry.frames, camera_pixel_range=telemetry.pixel_range,
                            camera_width=telemetry.width, camera_height=telemetry.height,
                            remote_stop_steps=telemetry.remote_stop_steps, remote_interventions=telemetry.remote_interventions,
                            control_failures=telemetry.control_failures, brain_steps=telemetry.brain_steps, interventions=telemetry.interventions,
                            navigation_steps=telemetry.navigation_steps, recoveries=telemetry.recoveries,
                            passed_obstacles=sum(start[0] < node.getPosition()[0] < x - 1.0 for node in [obstacle] + extra_boxes + extra_people),
                            stop_steps=telemetry.stop_steps, brain_failures=telemetry.brain_failures,
                            max_looming=telemetry.max_looming, final_forward=telemetry.final_forward)
            print("REFLEXGUARD_RESULT=" + result.model_dump_json(), flush=True)
            sim.step(dt)  # let Webots drain controller stdout before shutdown
            sim.simulationQuit(0)
            return


if __name__ == "__main__":
    main()
