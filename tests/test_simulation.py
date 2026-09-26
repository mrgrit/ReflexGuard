"""Simulation math, input validation and failed-run detection."""
import json
import math
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError
from reflexguard.simulation.drive import CameraFrame, FrameSink, wheel_speeds
from reflexguard.simulation.geometry import box_clearance, circle_clearance
from reflexguard.simulation.models import Settings
from reflexguard.simulation.runner import read_result

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("forward,turn", [(0.6,0),(-0.6,0),(0,0.8),(0,-0.8),(0.6,0.8)])
def test_wheel_speed_limit_and_turn_sign(forward, turn):
    left, right = wheel_speeds(forward, turn, 0.6)
    assert max(abs(left), abs(right)) <= 2.5
    assert math.isclose(left+right,0) if forward == 0 else (left+right)*forward > 0
    assert math.isclose(left,right) if turn == 0 else (right-left)*turn > 0

@pytest.mark.parametrize("value", [float("nan"),float("inf"),-1,0,3.1])
def test_bad_max_speed_rejected(value):
    with pytest.raises(ValueError):
        wheel_speeds(0.5, 0, value)

def test_releasing_keys_stops_motors():
    assert wheel_speeds(0,0,0.6) == (0,0)

def test_camera_requires_complete_bgra_and_ignores_alpha():
    sink=FrameSink()
    sink.consume(CameraFrame(32,2,1,bytes([0,0,0,255,0,0,0,255])))
    assert sink.pixel_range == 0
    sink.consume(CameraFrame(64,2,1,bytes([0,0,0,255,200,0,0,255])))
    assert sink.pixel_range == 200
    with pytest.raises(ValueError):
        sink.consume(CameraFrame(96,2,1,b""))
    assert sink.frames == 2

@pytest.mark.parametrize("data", [{"world":"../../tmp/world"},{"duration_s":0},{"duration_s":61},
                                       {"drive":"unexpected"},{"unknown":True}])
def test_scenario_external_input_rejected(data):
    with pytest.raises(ValidationError):
        Settings(**data)

def test_conservative_clearance():
    assert circle_clearance(0,0,1,0,0.4) == 0
    assert circle_clearance(0,0,2,0,0.4) == pytest.approx(0.92)
    assert box_clearance(0,0,2,0,0.3,0.4) == pytest.approx(1.02)
    assert box_clearance(2,0,2,0,0.3,0.4) == 0

@pytest.fixture
def good_result():
    return dict(world="corridor_static",drive="forward",duration_s=10.016,collision=True,collision_events=1,
                min_clearance_estimate_m=0.0,displacement_m=3.0,yaw_change_rad=0.0,
                camera_frames=300,camera_pixel_range=100,camera_width=160,camera_height=120)

def test_valid_result_can_report_collision(good_result):
    assert read_result("REFLEXGUARD_RESULT="+json.dumps(good_result)).collision

@pytest.mark.parametrize("change", [{"camera_frames":0},{"camera_pixel_range":0},{"displacement_m":0.0},
                                    {"collision":False},{"duration_s":float("nan")}])
def test_incomplete_or_inconsistent_result_fails(good_result,change):
    good_result.update(change)
    with pytest.raises(ValueError):
        read_result("REFLEXGUARD_RESULT="+json.dumps(good_result))

@pytest.mark.parametrize("prefix", ["ERROR: simulation failed\n", "Traceback (most recent call last):\n"])
def test_simulator_error_is_not_success(good_result,prefix):
    with pytest.raises(ValueError):
        read_result(prefix+"REFLEXGUARD_RESULT="+json.dumps(good_result))

@pytest.mark.parametrize("log", ["", "INFO: controller exited successfully.", "REFLEXGUARD_RESULT={}\nREFLEXGUARD_RESULT={}"])
def test_missing_or_duplicate_result_fails(log):
    with pytest.raises(ValueError):
        read_result(log)

@pytest.mark.parametrize("args", [["../../etc/passwd"],["corridor_static","0"],["corridor_static","61"],
                                  ["corridor_static","1","bad"],["corridor_static;echo"]])
def test_shell_launcher_rejects_before_starting_webots(args):
    completed=subprocess.run(["/bin/bash",str(ROOT/"scripts/run_scenario.sh"),*args],capture_output=True,timeout=5)
    assert completed.returncode == 2
    assert completed.stdout == b""


def test_runtime_uses_checkout_venv_without_resolving_symlink(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location("configure_webots",ROOT/"scripts/configure_webots.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError):
        module.configure(tmp_path)
    interpreter=tmp_path/".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to("/usr/bin/python3")
    for name in ("wheelchair","scenario"):
        directory=tmp_path/"webots/controllers"/name
        directory.mkdir(parents=True)
        (directory/"runtime.ini.in").write_text("[python]\nCOMMAND = @PYTHON@\n")
    worlds=tmp_path/'webots/worlds'
    worlds.mkdir()
    template=worlds/'corridor_demo.wbproj.in'
    template.write_text('renderingDevicePerspectives: camera;1;1;0.2;0.5\n')
    module.configure(tmp_path)
    layout=worlds/'.corridor_demo.wbproj'
    assert layout.read_text()==template.read_text()
    layout.write_text('renderingDevicePerspectives: camera;1;1;0;0\n')
    module.configure(tmp_path)
    assert layout.read_text()==template.read_text()
    custom='renderingDevicePerspectives: camera;1;1;0.6;0.7\n'
    layout.write_text(custom)
    module.configure(tmp_path)
    assert layout.read_text()==custom
    for name in ("wheelchair","scenario"):
        assert str(interpreter) in (tmp_path/"webots/controllers"/name/"runtime.ini").read_text()


def test_contacts_require_matching_hazard_not_floor_or_own_node_id():
    from reflexguard.simulation.geometry import has_hazard_contact
    floor=[(0.0,0.0,0.0)]
    assert not has_hazard_contact(floor, [])
    assert not has_hazard_contact(floor, [(1.0,0.0,0.0)])
    assert has_hazard_contact([(0.0,0.0,0.5)],[(0.0,0.0,0.5)])
    # A genuine low obstacle contact must not be filtered just by its height.
    assert has_hazard_contact(floor, [(0.0,0.0,0.0)])
