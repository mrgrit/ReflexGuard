"""Runtime-only secrets and ephemeral certificates; never commit credentials."""

from pathlib import Path
import secrets
import subprocess

from fastapi.testclient import TestClient
import pytest

from reflexguard.common.config import ClientSettings, MockSettings
from reflexguard.mock_brain.app import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def credentials():
    return {
        name: {"token": secrets.token_urlsafe(32), "role": role, "subject": subject}
        for name, role, subject in (
            ("guardian", "guardian", "seat-a"),
            ("operator", "operator", "seat-a"),
            ("admin", "admin", "seat-a"),
            ("outsider", "operator", "seat-b"),
        )
    }


@pytest.fixture
def mock_settings(credentials):
    return MockSettings(tokens=list(credentials.values()))


@pytest.fixture
def api(mock_settings, credentials):
    with TestClient(
        create_app(mock_settings), base_url="https://localhost",
        headers={"Authorization": "Bearer " + credentials["operator"]["token"]},
        raise_server_exceptions=False,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    directory = tmp_path_factory.mktemp("tls") / "certs"
    subprocess.run(
        ["/bin/bash", str(ROOT / "scripts/gen_certs.sh"), str(directory)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return directory


@pytest.fixture(scope="session")
def untrusted_certificates(tmp_path_factory):
    directory = tmp_path_factory.mktemp("untrusted-tls") / "certs"
    subprocess.run(
        ["/bin/bash", str(ROOT / "scripts/gen_certs.sh"), str(directory)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return directory


@pytest.fixture
def client_settings(certificates, credentials):
    return ClientSettings(
        base_url="https://localhost:8443", token=credentials["operator"]["token"],
        ca_cert=certificates / "ca.crt", client_cert=certificates / "client.crt",
        client_key=certificates / "client.key",
    )
