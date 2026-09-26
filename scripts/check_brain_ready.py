"""Read-only authenticated readiness check before creating a Webots controller."""
import asyncio
import logging
import os
from typing import Literal

from pydantic import TypeAdapter

from reflexguard.brain_client.client import BrainClient, BrainClientError
from reflexguard.common.config import ConfigurationError

LOGGER = logging.getLogger(__name__)


async def check(client=None, profile=None):
    profile = TypeAdapter(Literal["real", "local", "mock"]).validate_python(
        profile if profile is not None else os.environ.get("REFLEXGUARD_BRAIN_PROFILE", "mock"))
    owned = client is None
    client = BrainClient() if owned else client
    try:
        # Only health is retried, while the simulator has not started. Never retry steps.
        for attempt in range(3):
            try:
                health = await client.health()
                prefix = "mock-" if profile == "mock" else "malecns-"
                if not health.model_version.startswith(prefix):
                    raise ConfigurationError("Unexpected brain profile")
                return health
            except BrainClientError:
                if attempt == 2:
                    raise
                await asyncio.sleep(.2)
    finally:
        if owned:
            await client.aclose()


def main():
    try:
        health = asyncio.run(check())
    except (BrainClientError, ConfigurationError, ValueError) as exc:
        LOGGER.error("Brain startup check failed (%s)", type(exc).__name__)
        raise SystemExit(1) from None
    print("Brain ready: " + health.model_version)


if __name__ == "__main__":
    main()
