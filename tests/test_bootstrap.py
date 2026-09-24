"""The bootstrap preview must not invoke privileged or network operations."""

from pathlib import Path
import os
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.sh"


@pytest.fixture(autouse=True)
def block_installation_commands(tmp_path, monkeypatch):
    """A preview regression must fail without installing anything on the host."""
    command_dir = tmp_path / "blocked-commands"
    command_dir.mkdir()
    for name in ("sudo", "pkexec", "apt-get", "curl", "git", "pipx"):
        command = command_dir / name
        command.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        command.chmod(0o755)
    monkeypatch.setenv("PATH", str(command_dir) + os.pathsep + os.environ["PATH"])


def invoke(*args):
    return subprocess.run(
        ["/bin/bash", str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_help_is_available_without_installing():
    result = invoke("--help")
    assert result.returncode == 0
    assert "Ubuntu 22.04" in result.stdout


def test_dry_run_preserves_missing_destination(tmp_path):
    destination = tmp_path / "uncreated checkout"
    result = invoke("--dry-run", "--prefix", str(destination))
    assert result.returncode == 0
    assert str(destination) in result.stdout
    assert not destination.exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--unknown"],
        ["--prefix"],
        ["--prefix", "relative"],
        ["--prefix", "/"],
        ["--prefix", "/tmp/.."],
        ["--prefix", os.path.expanduser("~")],
    ],
)
def test_invalid_arguments_fail_before_installation(args):
    result = invoke(*args)
    assert result.returncode == 2
    assert result.stderr
