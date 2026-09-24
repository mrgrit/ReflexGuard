"""Device-side failure handling, response bounds and remote motor safety."""
import asyncio
import secrets
from types import SimpleNamespace
import httpx
import pytest
from reflexguard.control_server.device_client import DeviceClient, DeviceSettings
from reflexguard.control_server.schemas import RemoteRequest
from reflexguard.control_server.signing import sign_command
from reflexguard.control.arbiter import Command

@pytest.fixture
def device(certificates):
    return DeviceClient(DeviceSettings(url="https://localhost:8444",chair_id="seat-a",token=secrets.token_urlsafe(32),
                        hmac_key=secrets.token_urlsafe(32),ca_cert=certificates/"ca.crt"))

@pytest.mark.parametrize("mode",["network","timeout","invalid","oversized","compressed","forged"])
def test_poll_failure_stops_and_latches(device,mode):
    async def run():
        async def handler(request):
            if mode=="network":raise httpx.ConnectError("failed")
            if mode=="timeout":await asyncio.sleep(.3)
            if mode=="invalid":return httpx.Response(200,json={"command":{},"silence":None})
            if mode=="oversized":return httpx.Response(200,content=b"x"*32769)
            if mode=="compressed":return httpx.Response(200,headers={"Content-Encoding":"deflate"},content=b"")
            env=sign_command(RemoteRequest(chair_id="seat-a",action="stop"),device.boot_id,secrets.token_urlsafe(32),0)
            return httpx.Response(200,json={"command":env.model_dump(),"silence":None})
        await device.client.aclose()
        device.client=httpx.AsyncClient(transport=httpx.MockTransport(handler),base_url="https://localhost:8444")
        await device.poll(SimpleNamespace())
        assert device.failed and device.guard.stopped
        assert device.guard.apply(Command(forward=.6,turn=1.0))==Command(forward=0.0,turn=0.0)
        await device.poll(SimpleNamespace())
        assert device.failed
        await device.close()
    asyncio.run(run())

def test_valid_stop_then_acknowledgement(device):
    async def run():
        import time
        from reflexguard.control_server.schemas import SignedRemote
        envelope=sign_command(RemoteRequest(chair_id="seat-a",action="stop"),device.boot_id,device.settings.hmac_key.get_secret_value(),int(time.time()*1000))
        requests=[]
        def handler(request):
            import json
            requests.append(json.loads(request.content))
            return httpx.Response(200,json={"command":envelope.model_dump() if len(requests)==1 else None,"silence":None})
        await device.client.aclose()
        device.client=httpx.AsyncClient(transport=httpx.MockTransport(handler),base_url="https://localhost:8444")
        await device.poll(SimpleNamespace())
        await device.poll(SimpleNamespace())
        assert requests[1]["acknowledged"]==envelope.body.nonce
        assert device.guard.stopped and not device.failed
        await device.close()
    asyncio.run(run())

def test_tls_trust_is_required(certificates,tmp_path):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DeviceSettings(url="http://localhost:8444",chair_id="seat-a",token=secrets.token_urlsafe(32),hmac_key=secrets.token_urlsafe(32),ca_cert=certificates/"ca.crt")
