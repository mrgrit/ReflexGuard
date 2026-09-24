"""Bounded HTTPS device connection; invalid commands or lost control connection latch a stop."""
import asyncio
import os
import secrets
import ssl
import time
import httpx
from pydantic import BaseModel, ConfigDict, FilePath, SecretStr, AnyHttpUrl, field_validator
from reflexguard.common.config import ClientSettings, TokenRecord
from reflexguard.common.schemas import Identifier
from reflexguard.control_server.schemas import PollResponse, DecisionInput
from reflexguard.control_server.signing import RemoteGuard

class DeviceSettings(BaseModel):
    model_config=ConfigDict(extra="forbid",hide_input_in_errors=True,frozen=True)
    url: AnyHttpUrl
    chair_id: Identifier
    token: SecretStr
    hmac_key: SecretStr
    ca_cert: FilePath

    @field_validator("url")
    @classmethod
    def origin(cls,value):
        return ClientSettings.https_origin_only(value)

    @field_validator("token","hmac_key")
    @classmethod
    def secret(cls,value):
        return TokenRecord.strong_token(value)

    @classmethod
    def from_env(cls):
        return cls(url=os.environ["REFLEXGUARD_CONTROL_URL"],chair_id=os.environ["REFLEXGUARD_CHAIR_ID"],
                   token=os.environ["REFLEXGUARD_DEVICE_TOKEN"],hmac_key=os.environ["REFLEXGUARD_REMOTE_KEY"],
                   ca_cert=os.environ["REFLEXGUARD_TLS_CA"])

class DeviceClient:
    def __init__(self, settings):
        self.boot_id=secrets.token_urlsafe(32)
        self.settings=settings
        self.guard=RemoteGuard(settings.chair_id,settings.hmac_key.get_secret_value(),self.boot_id)
        context=ssl.create_default_context(cafile=str(settings.ca_cert))
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        self.client=httpx.AsyncClient(base_url=str(settings.url),verify=context,timeout=.2,trust_env=False,
            follow_redirects=False,headers={"Authorization":"Bearer "+settings.token.get_secret_value(),"Accept-Encoding":"identity"})
        self.sequence=0
        self.failed=False

    async def exchange(self, suffix, body):
        async with self.client.stream("POST",f"/device/{self.settings.chair_id}/{suffix}",json=body) as response:
            response.raise_for_status()
            if response.headers.get("content-encoding","identity")!="identity":
                raise ValueError("Unexpected encoding")
            content=bytearray()
            async for part in response.aiter_bytes():
                content.extend(part)
                if len(content)>32768:
                    raise ValueError("Oversized response")
            return bytes(content)

    async def request(self,suffix,body):
        return await asyncio.wait_for(self.exchange(suffix,body),.2)

    def fail(self):
        self.failed=True
        self.guard.stopped=True

    async def start(self):
        try:
            await self.request("hello",{"boot_id":self.boot_id})
        except (httpx.HTTPError,ValueError,asyncio.TimeoutError):
            self.fail()

    async def poll(self, pipeline):
        if self.failed:
            return
        try:
            raw=await self.request("poll",{"boot_id":self.boot_id,"acknowledged":self.guard.acknowledged})
            response=PollResponse.model_validate_json(raw)
            if response.command is not None:
                self.guard.accept(response.command)
            if response.silence is not None:
                # Uses the controller's existing mTLS session and server-side allowlist.
                await pipeline.client.silence(pipeline.session_id,response.silence.neuron_ids)
        except (httpx.HTTPError,ValueError,asyncio.TimeoutError,RuntimeError):
            self.fail()

    async def report(self, *, t_ms, result, command, reason, top_neurons, model_version):
        if self.failed:
            return
        self.sequence+=1
        body=DecisionInput(boot_id=self.boot_id,sequence=self.sequence,t_ms=t_ms,
            left_looming=result.looming.left,right_looming=result.looming.right,escape=result.escape,
            top_neurons=top_neurons,model_version=model_version,reason=reason,
            forward=command.forward,turn=command.turn,remote_stopped=self.guard.stopped)
        try:
            await self.request("decisions",body.model_dump())
        except (httpx.HTTPError,ValueError,asyncio.TimeoutError):
            self.fail()

    async def close(self):
        await self.client.aclose()
