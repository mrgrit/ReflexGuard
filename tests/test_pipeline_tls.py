"""Disconnect a real authenticated TLS service while shared control is moving."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

from reflexguard.brain_client.client import BrainClient, BrainClientError
from reflexguard.common.config import ClientSettings
from reflexguard.control.arbiter import Command
from reflexguard.control.config import Calibration
from reflexguard.control.pipeline import Pipeline
from reflexguard.simulation.drive import CameraFrame

ROOT=Path(__file__).resolve().parents[1]


def test_real_mtls_disconnect_causes_latched_gradual_stop(certificates,tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    token=secrets.token_urlsafe(32)
    env={**os.environ,"PYTHONPATH":str(ROOT/"src"),"REFLEXGUARD_MOCK_PORT":str(port),
         "REFLEXGUARD_API_TOKENS":json.dumps([{"token":token,"subject":"pipeline-test","role":"operator"}]),
         "REFLEXGUARD_TLS_CA":str(certificates/"ca.crt"),
         "REFLEXGUARD_TLS_SERVER_CERT":str(certificates/"server.crt"),
         "REFLEXGUARD_TLS_SERVER_KEY":str(certificates/"server.key")}
    settings=ClientSettings(base_url=f"https://localhost:{port}",token=token,
                            ca_cert=certificates/"ca.crt",client_cert=certificates/"client.crt",
                            client_key=certificates/"client.key")
    with (tmp_path/"server.log").open("w") as log:
        process=subprocess.Popen([str(ROOT/".venv/bin/python"),"-m","reflexguard.mock_brain"],
                                 cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            async def run():
                client=BrainClient(settings)
                deadline=time.monotonic()+10
                while True:
                    try:
                        await client.health()
                        break
                    except BrainClientError:
                        if process.poll() is not None or time.monotonic()>deadline:
                            raise RuntimeError("Test server failed to start")
                        await asyncio.sleep(0.03)
                pipe=Pipeline(Calibration(),client)
                try:
                    await pipe.start()
                    user=Command(forward=0.6,turn=0.0)
                    pixels=bytes([220,220,220,255])*(160*120)
                    before=await pipe.step(CameraFrame(0,160,120,pixels),user,32)
                    assert before.decision.command.forward==0.6
                    process.kill()  # abrupt outage of this test-owned server
                    process.wait(timeout=5)
                    first=await pipe.step(CameraFrame(32,160,120,pixels),user,32)
                    assert 0<first.decision.command.forward<0.6
                    for i in range(2,20):
                        last=await pipe.step(CameraFrame(i*32,160,120,pixels),user,32)
                    assert last.decision.command.forward==0
                    assert last.decision.reason=="brain_failure"
                    assert pipe.failures==1 and pipe.brain_steps==1
                finally:
                    await pipe.close()
            asyncio.run(run())
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
