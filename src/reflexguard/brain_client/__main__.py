"""One authenticated health/session/step exchange against the configured brain."""

import asyncio
import json

from reflexguard.brain_client.client import BrainClient
from reflexguard.common.schemas import StepRequest


async def smoke():
    async with BrainClient() as client:
        health = await client.health()
        session = await client.create_session()
        response = await client.step(session.session_id, StepRequest(
            t_ms=0, dt_ms=50, left_looming=0.9, right_looming=0.1,
        ))
        print(json.dumps({
            "health": health.model_dump(), "step": response.model_dump(),
        }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(smoke())
