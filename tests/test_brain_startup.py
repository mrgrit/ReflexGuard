"""Startup health checks do not allocate sessions or bypass the chosen model."""
import asyncio
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from reflexguard.brain_client.client import BrainClientError
from reflexguard.common.config import ConfigurationError
from reflexguard.common.schemas import HealthResponse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_brain_ready", ROOT / "scripts/check_brain_ready.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


def health(version="malecns-test"):
    return HealthResponse(status="ok", model_version=version, weights_sha256="0" * 64)


def test_readiness_retries_health_without_creating_or_advancing_session():
    client = AsyncMock()
    client.health.side_effect = [BrainClientError("Unavailable"), health()]
    assert asyncio.run(startup.check(client, "real")) == health()
    assert client.health.await_count == 2
    client.create_session.assert_not_awaited()
    client.step.assert_not_awaited()


def test_unavailable_server_has_bounded_startup_failure():
    client = AsyncMock()
    client.health.side_effect = BrainClientError("Unavailable")
    with pytest.raises(BrainClientError):
        asyncio.run(startup.check(client, "real"))
    assert client.health.await_count == 3


@pytest.mark.parametrize("profile", ["real", "local"])
def test_real_profile_cannot_accept_mock_health(profile):
    client = AsyncMock()
    client.health.return_value = health("mock-rules-v1")
    with pytest.raises(ConfigurationError):
        asyncio.run(startup.check(client, profile))
    assert client.health.await_count == 1


def test_invalid_profile_rejected_before_network():
    client = AsyncMock()
    with pytest.raises(ValidationError):
        asyncio.run(startup.check(client, "other"))
    client.health.assert_not_awaited()


@pytest.mark.parametrize("profile,ready,service_ok,expected", [
    ("local", True, False, 0), ("local", False, True, 0), ("local", False, False, 1),
    ("real", True, False, 0), ("real", False, True, 0),
    ("real", False, False, 1), ("mock", False, True, 1),
])
def test_launcher_checks_brain_before_opening_window(tmp_path, profile, ready, service_ok, expected):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/run_webots.sh", scripts / "run_webots.sh")
    (scripts / "brain_profile.sh").write_text(":\n")
    interpreter = tmp_path / ".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text('#!/bin/sh\ncase "$1" in\n*check_brain_ready.py) test -f READY;;\n*) exit 0;;\nesac\n')
    interpreter.chmod(0o755)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    service = binaries / "systemctl"
    service.write_text('#!/bin/sh\ntouch SERVICE_CALLED\n' + ('touch READY\n' if service_ok else 'exit 1\n'))
    service.chmod(0o755)
    webots = binaries / "webots"
    webots.write_text('#!/bin/sh\ntouch WINDOW_OPENED\n')
    webots.chmod(0o755)
    if ready:
        (tmp_path / "READY").touch()
    result = subprocess.run(["bash", str(scripts / "run_webots.sh")], cwd=tmp_path,
                            env=dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                                     REFLEXGUARD_BRAIN_PROFILE=profile), capture_output=True, timeout=5)
    assert result.returncode == expected
    assert (tmp_path / "WINDOW_OPENED").exists() == (expected == 0)
    assert (tmp_path / "SERVICE_CALLED").exists() == (profile in ("real", "local") and not ready)
