"""Observe contacts and finish bounded batch runs without controlling motors."""
import math
import os
from controller import Supervisor
from reflexguard.simulation.models import Settings, Telemetry, Result
from reflexguard.simulation.geometry import box_clearance, circle_clearance, PEDESTRIAN_RADIUS, has_hazard_contact

# Geometry matches the fixed corridor walls; the gap is the side doorway.
WALLS = [(0.0, -1.6, 6.0, 0.1), (-4.25, 1.6, 1.75, 0.1),
         (2.75, 1.6, 3.25, 0.1), (-6.0, 0.0, 0.1, 1.6), (6.0, 0.0, 0.1, 1.6)]


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
    start = chair.getPosition()
    initial_orientation = chair.getOrientation()
    initial_yaw = math.atan2(initial_orientation[3], initial_orientation[0])
    minimum = 100.0
    events = 0
    previous_contact = False
    while sim.step(dt) != -1:
        x, y, _ = chair.getPosition()
        ox, oy, _ = obstacle.getPosition()
        distances = [box_clearance(x, y, *wall) for wall in WALLS]
        if world == "corridor_static":
            distances.append(box_clearance(x, y, ox, oy, 0.3, 0.4))
        else:
            distances.append(circle_clearance(x, y, ox, oy, PEDESTRIAN_RADIUS))
        minimum = min(minimum, *distances)
        contact = has_hazard_contact(
            [point.point for point in chair.getContactPoints(True)],
            [point.point for hazard in hazards for point in hazard.getContactPoints(True)],
        )
        if contact and not previous_contact:
            events += 1
        previous_contact = contact
        if settings.batch and sim.getTime() >= settings.duration_s:
            telemetry = Telemetry.model_validate_json(chair.getBaseNodeField("customData").getSFString())
            orientation = chair.getOrientation()
            yaw = math.atan2(orientation[3], orientation[0]) - initial_yaw
            result = Result(world=world, drive=settings.drive, duration_s=sim.getTime(),
                            collision=events > 0, collision_events=events,
                            min_clearance_estimate_m=minimum, displacement_m=math.hypot(x-start[0], y-start[1]),
                            yaw_change_rad=math.atan2(math.sin(yaw), math.cos(yaw)),
                            camera_frames=telemetry.frames, camera_pixel_range=telemetry.pixel_range,
                            camera_width=telemetry.width, camera_height=telemetry.height)
            print("REFLEXGUARD_RESULT=" + result.model_dump_json(), flush=True)
            sim.step(dt)  # let Webots drain controller stdout before shutdown
            sim.simulationQuit(0)
            return


if __name__ == "__main__":
    main()
