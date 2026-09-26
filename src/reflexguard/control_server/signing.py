"""Canonical authenticated command envelopes with boot-bound replay defense."""
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated
from pydantic import Field, TypeAdapter
from reflexguard.control_server.schemas import RemoteBody, SignedRemote, RemoteRequest

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()

def mac(key, value):
    return hmac.new(key.encode(), canonical(value), hashlib.sha256).hexdigest()

def sign_command(request: RemoteRequest, boot_id: str, key: str, now_ms: int):
    body=RemoteBody(**request.model_dump(), boot_id=boot_id, issued_ms=now_ms, nonce=secrets.token_urlsafe(32))
    return SignedRemote(body=body, signature=mac(key, body.model_dump()))

class RemoteGuard:
    def __init__(self, chair_id, key, boot_id, max_speed=0.6):
        self.max_speed=TypeAdapter(Annotated[float, Field(strict=True, gt=0, le=6.0, allow_inf_nan=False)]).validate_python(max_speed)
        self.chair_id=chair_id
        self.key=key
        self.boot_id=boot_id
        self.used={}
        self.stopped=False
        self.speed_limit=self.max_speed
        self.acknowledged=None

    def accept(self, envelope: SignedRemote, now_ms=None):
        envelope=SignedRemote.model_validate(envelope)
        now_ms=int(time.time()*1000) if now_ms is None else now_ms
        body=envelope.body
        if (body.chair_id!=self.chair_id or body.boot_id!=self.boot_id
                or abs(now_ms-body.issued_ms)>2000
                or not hmac.compare_digest(envelope.signature, mac(self.key, body.model_dump()))):
            raise ValueError("Invalid remote command")
        self.used={nonce:stamp for nonce,stamp in self.used.items() if stamp>=now_ms-2000}
        if body.nonce in self.used or len(self.used)>=1024:
            raise ValueError("Remote command replay or capacity exceeded")
        self.used[body.nonce]=body.issued_ms
        if body.action=="stop":
            self.stopped=True
        else:
            self.speed_limit=min(self.max_speed, body.speed_limit)
        self.acknowledged=body.nonce

    def apply(self, command):
        from reflexguard.control.arbiter import Command
        command=Command.model_validate(command)
        if self.stopped:
            return Command(forward=0.0, turn=0.0)
        # Bound both wheels: radius=.24m, track=.64m; wheel linear speeds are v ± omega*.32.
        wheel_peak=max(abs(command.forward-command.turn*0.32), abs(command.forward+command.turn*0.32))
        scale=min(1.0, self.speed_limit/wheel_peak) if wheel_peak else 1.0
        return Command(forward=command.forward*scale, turn=command.turn*scale)
