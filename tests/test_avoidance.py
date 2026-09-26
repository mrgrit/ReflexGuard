"""Sensor bounds, user authority, clear-path motion, and latched failure stops."""
import math
import pytest
from pydantic import ValidationError
from reflexguard.control.avoidance import LocalAvoidance, Surroundings
from reflexguard.control.arbiter import Command
from reflexguard.control.config import Calibration
from reflexguard.decoder.decoder import Signal


def scan(t=32, distance=math.inf):
    return Surroundings(t_ms=t, heading=0.0, ranges=[[distance] * 64 for _ in range(4)])


def test_brain_hazard_allows_cautious_progress_only_with_valid_clear_ranges():
    navigator = LocalAvoidance(Calibration())
    user = Command(forward=2.0, turn=0.0)
    result = navigator.update(user, Signal.STOP, .8, 32, True, scan(), 32)
    assert 0 < result.command.forward < user.forward
    assert result.reason == "risk_monitoring"


def test_surrounded_chair_stops_instead_of_selecting_unsafe_turn():
    navigator = LocalAvoidance(Calibration())
    result = navigator.update(Command(forward=3.0, turn=1.0), Signal.STOP, .8, 32, True, scan(distance=.05), 32)
    assert result.command == Command(forward=0.0, turn=0.0)
    assert result.reason == "path_blocked"


def test_neutral_user_never_starts_autonomous_driving():
    navigator = LocalAvoidance(Calibration())
    result = navigator.update(Command(forward=0.0, turn=0.0), Signal.STOP, 1.0, 32, True, scan(), 32)
    assert result.command == Command(forward=0.0, turn=0.0) and not result.intervened


@pytest.mark.parametrize("failure", ["missing", "stale", "brain"])
def test_sensor_or_brain_failure_decelerates_and_latches(failure):
    navigator = LocalAvoidance(Calibration())
    user = Command(forward=2.0, turn=0.0)
    navigator.update(user, Signal.NONE, 0.0, 32, True, scan(), 32)
    broken = None if failure == "missing" else scan(32 if failure == "stale" else 64)
    previous = 2.0
    for i in range(1, 40):
        now = 32 + i * 32
        result = navigator.update(user, Signal.NONE, 0.0, 32, failure != "brain" if i == 1 else True,
                                  broken if i == 1 else scan(now), now)
        assert 0 <= result.command.forward <= previous
        previous = result.command.forward
    assert previous == 0 and navigator.fault


@pytest.mark.parametrize("value", [float("nan"), -math.inf, -1.0, 0.0, 8.1, True])
def test_invalid_sensor_values_rejected(value):
    with pytest.raises(ValidationError):
        scan(distance=value)


def test_range_count_and_heading_are_bounded():
    with pytest.raises(ValidationError):
        Surroundings(t_ms=32, heading=0.0, ranges=[[1.0] * 63] * 4)
    with pytest.raises(ValidationError):
        Surroundings(t_ms=32, heading=math.inf, ranges=[[1.0] * 64] * 4)


def test_sensor_points_keep_left_right_and_mount_offsets():
    rows = [[math.inf] * 64 for _ in range(4)]
    rows[0][0] = 1.0
    points = Surroundings(t_ms=32, heading=0.0, ranges=rows).points()
    assert points[0, 0] == pytest.approx(1.12)
    assert points[0, 1] > 0


@pytest.mark.parametrize("moving", [False, True])
def test_closed_loop_passes_circle_obstacle_and_restores_heading(moving):
    import numpy as np
    from reflexguard.control.avoidance import MOUNTS, wrapped
    navigator = LocalAvoidance(Calibration())
    x, y, heading = 0.0, 0.0, 0.0
    recovered = False
    turned = False
    travel = 0.0
    rotation = 0.0
    for step in range(1, 251):
        obstacle_y = -1.5 + .5 * step * .1 if moving else 0.0
        readings = []
        for mx, my, yaw in MOUNTS:
            sx = x + mx * math.cos(heading) - my * math.sin(heading)
            sy = y + mx * math.sin(heading) + my * math.cos(heading)
            row = []
            for angle in np.linspace(math.pi / 3, -math.pi / 3, 64):
                direction = heading + yaw + angle
                dx, dy = math.cos(direction), math.sin(direction)
                # Ray/circle intersection for a stationary obstacle centered at (4, 0).
                projection = (4 - sx) * dx + (obstacle_y - sy) * dy
                discriminant = projection ** 2 - ((4 - sx) ** 2 + (obstacle_y - sy) ** 2 - .5 ** 2)
                hit = projection - math.sqrt(discriminant) if discriminant >= 0 else math.inf
                row.append(hit if .02 <= hit <= 8 else math.inf)
            readings.append(row)
        sensed = Surroundings(t_ms=step * 100, heading=heading, ranges=readings, travel_m=travel, forward_mps=travel * 10, turn_rad_s=rotation)
        decision = navigator.update(Command(forward=2.0, turn=0.0), Signal.STOP, .6, 100, True, sensed, step * 100)
        turned = turned or abs(decision.command.turn) > .1
        recovered = recovered or decision.reason == "control_recovered"
        travel = decision.command.forward * .1
        x += decision.command.forward * math.cos(heading) * .1
        y += decision.command.forward * math.sin(heading) * .1
        rotation = decision.command.turn
        heading = wrapped(heading + rotation * .1)
        # Independent circular enclosure check, stricter than visual center overlap.
        assert math.hypot(x - 4, y - obstacle_y) > 1.0
        if x > 8 and recovered and abs(heading) < .15 and abs(y) < .4:
            break
    assert x > 8 and turned and recovered
    assert abs(heading) < .15
    assert abs(y) < .4


def test_motion_estimate_removes_ego_translation_and_detects_crossing():
    import numpy as np
    navigator=LocalAvoidance(Calibration())
    shape=np.array([[0.,-.2],[0.,-.1],[0.,0.],[0.,.1],[0.,.2]])
    for index in range(1,25):
        sample=scan(index*32).model_copy(update={'travel_m':.064,'forward_mps':2.0})
        points=shape+np.array([4.-index*.064,1.-index*.0192])
        velocity=navigator.motion(points,sample)
    assert np.max(np.abs(velocity[:,0]))<.01
    assert np.allclose(velocity[:,1],-.6,atol=.02)


def test_stationary_object_does_not_move_when_chair_rotates():
    import numpy as np
    navigator=LocalAvoidance(Calibration())
    shape=np.array([[3.,-.2],[3.,-.1],[3.,0.],[3.,.1],[3.,.2]])
    for index in range(1,20):
        angle=index*.02
        rotation=np.array([[math.cos(angle),math.sin(angle)],[-math.sin(angle),math.cos(angle)]])
        sample=scan(index*32).model_copy(update={'heading':angle})
        velocity=navigator.motion(shape@rotation.T,sample)
    assert np.max(np.abs(velocity))<.001


def test_constructed_invalid_surroundings_cannot_skip_validation():
    broken=Surroundings.model_construct(t_ms=32,heading=float('nan'),ranges=[[math.inf]*64]*4)
    navigator=LocalAvoidance(Calibration())
    result=navigator.update(Command(forward=2.0,turn=0.0),Signal.NONE,0.0,32,True,broken,32)
    assert result.reason=='sensor_failure' and navigator.fault


@pytest.mark.parametrize("faulty_height", [0, 1])
def test_either_sensor_height_failure_prevents_fused_frame(faulty_height):
    rows = [[[math.inf] * 64 for _ in range(4)] for _ in range(2)]
    rows[0][0][32] = 3.0
    rows[1][0][32] = 1.0
    fused = Surroundings.from_heights(*rows, t_ms=32, heading=0.0)
    assert fused.ranges[0][32] == 1.0
    rows[faulty_height][0][32] = float("nan")
    with pytest.raises(ValidationError):
        Surroundings.from_heights(*rows, t_ms=32, heading=0.0)


def test_high_speed_reduces_near_obstacles_but_remains_available_in_open_space():
    config = Calibration(drive_speed=4.0)
    user = Command(forward=4.0, turn=0.0)
    navigator = LocalAvoidance(config)
    clear = navigator.update(user, Signal.NONE, 0.0, 32, True, scan(32), 32)
    assert clear.command.forward == 4.0
    rows = [[math.inf] * 64 for _ in range(4)]
    rows[0][20] = 5.0  # A near forward-side obstacle leaves the straight path clear.
    near = Surroundings(t_ms=64, heading=0.0, ranges=rows)
    limited = navigator.update(user, Signal.NONE, 0.0, 32, True, near, 64)
    assert limited.command.forward == 2.0 and limited.reason == 'risk_monitoring'


def test_slow_clearance_recovery_moves_away_from_side_obstacle(monkeypatch):
    import numpy as np
    monkeypatch.setattr(Surroundings, "points", lambda _: np.array([[0., .45]]))
    navigator = LocalAvoidance(Calibration())
    result = navigator.update(Command(forward=4., turn=0.), Signal.NONE, 0., 32, True, scan(32), 32)
    assert result.reason == "avoid_clearance_recovery"
    assert 0 < result.command.forward <= .3
    assert abs(result.command.turn) <= .4


def test_clearance_recovery_cannot_move_through_body_obstacle(monkeypatch):
    import numpy as np
    monkeypatch.setattr(Surroundings, "points", lambda _: np.array([[.60, 0.]]))
    navigator = LocalAvoidance(Calibration())
    result = navigator.update(Command(forward=4., turn=0.), Signal.NONE, 0., 32, True, scan(32), 32)
    assert result.reason == "path_blocked"
    assert result.command == Command(forward=0., turn=0.)
