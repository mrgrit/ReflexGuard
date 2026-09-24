"""Synthetic perception, shared-control state transitions and brain failure paths."""
import asyncio
import numpy as np
import pytest
from pydantic import ValidationError
from reflexguard.brain_client.client import BrainClientError
from reflexguard.common.schemas import StepResponse, SessionResponse
from reflexguard.control.arbiter import Arbiter, Command
from reflexguard.control.config import Calibration
from reflexguard.control.pipeline import Pipeline
from reflexguard.decoder.decoder import Decoder, Signal
from reflexguard.encoder.looming import LoomingEncoder
from reflexguard.mock_brain.rules import evaluate
from reflexguard.simulation.drive import CameraFrame


def frame(t, radius=0, side="left"):
    image=np.full((120,160,4),220,dtype=np.uint8)
    image[:,:,3]=255
    x=40 if side=="left" else 120
    image[60-radius:60+radius,x-radius:x+radius,:3]=40
    return CameraFrame(t,160,120,image.tobytes())


def response(escape=0.0,left=0.0,right=0.0):
    return StepResponse(escape=escape,turn_left=left,turn_right=right,top_neurons=[],model_version="test")


@pytest.mark.parametrize("side", ["left","right"])
def test_expanding_object_raises_looming_on_correct_side(side):
    encoder=LoomingEncoder(Calibration())
    values=[encoder.update(frame(i*32,8+i//2,side)) for i in range(40)]
    peaks=[max(getattr(value,side) for value in values)]
    assert peaks[0]>0.6
    other="right" if side=="left" else "left"
    assert max(getattr(value,other) for value in values)==0
    assert all(0<=value.left<=1 and 0<=value.right<=1 for value in values)


def test_stationary_and_shrinking_objects_do_not_loom():
    encoder=LoomingEncoder(Calibration())
    values=[encoder.update(frame(i*32,30-i//2)) for i in range(40)]
    assert all(value.left==0 and value.right==0 for value in values)


def test_ema_damps_one_frame_change_and_decays():
    encoder=LoomingEncoder(Calibration())
    encoder.update(frame(0,10))
    peak=encoder.update(frame(32,20)).left
    assert 0<peak<0.3
    for i in range(2,80):
        last=encoder.update(frame(i*32,20))
    assert last.left<0.01


@pytest.mark.parametrize("bad", [CameraFrame(0,160,120,b""), CameraFrame(-1,160,120,b""),
                                  CameraFrame(0,10000,120,b""), CameraFrame(0,161,120,b"")])
def test_invalid_camera_input_fails(bad):
    with pytest.raises(ValueError):
        LoomingEncoder(Calibration()).update(bad)


@pytest.mark.parametrize("time", [0,-1,101])
def test_replayed_or_stale_frame_fails(time):
    encoder=LoomingEncoder(Calibration())
    encoder.update(frame(0))
    with pytest.raises(ValueError):
        encoder.update(frame(time))


def test_decoder_stop_priority_and_hysteresis():
    decoder=Decoder(Calibration())
    assert decoder.update(response(0.31,0.9))==Signal.STOP
    assert decoder.update(response(0.2))==Signal.STOP
    assert decoder.update(response(0.12))==Signal.NONE


def test_decoder_turn_hysteresis_and_direction_switch():
    decoder=Decoder(Calibration())
    assert decoder.update(response(left=0.3))==Signal.LEFT
    assert decoder.update(response(left=0.15))==Signal.LEFT
    assert decoder.update(response(left=0.1))==Signal.NONE
    assert decoder.update(response(right=0.4))==Signal.RIGHT
    assert decoder.update(response(right=0.15))==Signal.RIGHT
    assert decoder.update(response(left=0.4))==Signal.LEFT
    assert decoder.update(response(left=0.5,right=0.5))==Signal.NONE


@pytest.mark.parametrize("data", [{"stop_on":0.1,"stop_off":0.2},{"turn_on":0.1,"turn_off":0.2},
                                 {"deceleration":0},{"expansion_scale":float("nan")},{"unknown":1}])
def test_invalid_calibration_rejected(data):
    with pytest.raises(ValidationError):
        Calibration(**data)


def test_user_passthrough_and_idle_no_spontaneous_turn():
    arbiter=Arbiter(Calibration())
    user=Command(forward=0.6,turn=0.2)
    assert arbiter.update(user,Signal.NONE,0.0,32).command==user
    idle=Command(forward=0.0,turn=0.0)
    for signal in Signal:
        result=arbiter.update(idle,signal,1.0,32)
        assert result.command==idle and not result.intervened


@pytest.mark.parametrize("signal,sign", [(Signal.LEFT,1),(Signal.RIGHT,-1)])
def test_turn_is_added_to_user_command_and_bounded(signal,sign):
    arbiter=Arbiter(Calibration())
    result=arbiter.update(Command(forward=0.4,turn=sign*1.0),signal,0.0,32)
    assert result.command.forward==0.4
    assert result.command.turn==sign*1.2
    assert result.intervened


@pytest.mark.parametrize("failure", [False,True])
def test_stop_ramps_to_zero_without_restart_on_held_input(failure):
    arbiter=Arbiter(Calibration())
    user=Command(forward=0.6,turn=0.4)
    arbiter.update(user,Signal.NONE,0.0,32)
    result=arbiter.update(user,Signal.STOP if not failure else Signal.NONE,0.0,32,healthy=not failure)
    assert 0<result.command.forward<0.6
    speeds=[result.command.forward]
    for _ in range(30):
        result=arbiter.update(user,Signal.NONE,0.0,32)
        speeds.append(result.command.forward)
    assert speeds==sorted(speeds,reverse=True)
    assert result.command==Command(forward=0.0,turn=0.0)
    assert result.reason==("brain_failure" if failure else "hazard_stop")


def test_hazard_rearms_only_after_neutral_and_fault_does_not_rearm():
    idle=Command(forward=0.0,turn=0.0)
    drive=Command(forward=0.6,turn=0.0)
    arbiter=Arbiter(Calibration())
    arbiter.update(drive,Signal.STOP,0.8,32)
    for _ in range(16): arbiter.update(idle,Signal.NONE,0.0,32)
    assert arbiter.update(drive,Signal.NONE,0.0,32).command==drive
    arbiter.update(drive,Signal.NONE,0.0,32,healthy=False)
    for _ in range(20): arbiter.update(idle,Signal.NONE,0.0,32)
    assert arbiter.update(drive,Signal.NONE,0.0,32).command==idle


def test_escape_threshold_stops_even_without_decoder_signal():
    arbiter=Arbiter(Calibration())
    result=arbiter.update(Command(forward=0.6,turn=0.0),Signal.NONE,0.9,32)
    assert result.command.forward==0 and result.reason=="hazard_stop"


class FakeBrain:
    def __init__(self, fail_at=None):
        self.requests=[]
        self.fail_at=fail_at
        self.closed=False
    async def health(self): pass
    async def create_session(self): return SessionResponse(session_id="test-session")
    async def step(self,session,request):
        if self.fail_at==len(self.requests): raise BrainClientError("Unavailable")
        self.requests.append(request)
        return evaluate(request,set())
    async def aclose(self): self.closed=True


def test_camera_brain_decoder_arbiter_pipeline_and_disconnect():
    async def run():
        brain=FakeBrain(fail_at=10)
        pipe=Pipeline(Calibration(),brain)
        await pipe.start()
        user=Command(forward=0.6,turn=0.0)
        for i in range(40):
            result=await pipe.step(frame(i*32,8),user,32)
        assert len(brain.requests)==10 and pipe.failures==1
        assert result.decision.reason=="brain_failure"
        assert result.decision.command.forward==0
        assert brain.requests[0].dt_ms==32
        await pipe.close()
        assert brain.closed
    asyncio.run(run())


def test_missing_camera_stops_before_brain_call():
    async def run():
        brain=FakeBrain()
        pipe=Pipeline(Calibration(),brain)
        await pipe.start()
        result=await pipe.step(None,Command(forward=0.6,turn=0.0),32)
        assert not brain.requests and pipe.failed
        assert result.decision.command.forward==0
        await pipe.close()
    asyncio.run(run())


def test_idle_pipeline_receives_risk_but_never_moves():
    async def run():
        pipe=Pipeline(Calibration(),FakeBrain())
        await pipe.start()
        idle=Command(forward=0.0,turn=0.0)
        for i in range(40):
            result=await pipe.step(frame(i*32,8+i//2),idle,32)
            assert result.decision.command==idle
        assert pipe.interventions==0 and pipe.brain_steps==40
        await pipe.close()
    asyncio.run(run())


@pytest.mark.parametrize("fault", ["collision","brain_failure","no_brain","idle_intervention"])
def test_completion_check_cannot_pass_without_real_safe_pipeline(fault):
    from reflexguard.simulation.models import Result
    from reflexguard.simulation.verify import verify
    data=dict(world="corridor_static",drive="idle",duration_s=3.0,collision=False,collision_events=0,
              min_clearance_estimate_m=0.8,displacement_m=0.003,yaw_change_rad=0.0,
              camera_frames=90,camera_pixel_range=100,camera_width=160,camera_height=120,brain_steps=90)
    if fault=="collision": data.update(collision=True,collision_events=1)
    if fault=="brain_failure": data["brain_failures"]=1
    if fault=="no_brain": data["brain_steps"]=0
    if fault=="idle_intervention": data["interventions"]=1
    with pytest.raises(ValueError): verify(Result(**data))


def test_constructed_invalid_command_is_revalidated():
    bad=Command.model_construct(forward=float("nan"),turn=0.0)
    with pytest.raises(ValueError):
        Arbiter(Calibration()).update(bad,Signal.NONE,0.0,32)
