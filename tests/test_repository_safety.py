"""Check that Git will not accidentally include local secrets or state."""

from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        "certs/client.key",
        "certs/ca.key",
        ".venv/bin/python",
        "state.db",
        "state.db-wal",
        "state.db-shm",
        "__pycache__/module.cpython-310.pyc",
    ],
)
def test_local_secrets_and_state_are_ignored(path):
    result = subprocess.run(
        ["/usr/bin/git", "check-ignore", "--no-index", "--quiet", "--", path],
        cwd=ROOT,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0


@pytest.mark.parametrize("path", [".env.example", "requirements.txt", "AGENTS.md"])
def test_reviewable_configuration_is_not_ignored(path):
    result = subprocess.run(
        ["/usr/bin/git", "check-ignore", "--no-index", "--quiet", "--", path],
        cwd=ROOT,
        check=False,
        timeout=5,
    )
    assert result.returncode == 1
