"""Local execution keeps model authentication, loopback binding and mandatory mTLS."""
import base64
import importlib.util
import json
from pathlib import Path
import secrets
import ssl

import pytest
from cryptography.exceptions import InvalidSignature
from test_brain_model import signed_assets  # noqa: F401 - shared signed synthetic fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_local_brain", ROOT / "scripts/run_local_brain.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


@pytest.fixture
def settings(signed_assets, certificates, monkeypatch):
    directory, key = signed_assets
    values = {
        "REFLEXGUARD_MODEL_DIR": str(directory),
        "REFLEXGUARD_MODEL_PUBLIC_KEY": base64.b64encode(key.public_key().public_bytes_raw()).decode(),
        "REFLEXGUARD_API_TOKENS": json.dumps([{"token": secrets.token_urlsafe(32), "subject": "local-test", "role": "operator"}]),
        "REFLEXGUARD_TLS_CA": str(certificates / "ca.crt"),
        "REFLEXGUARD_TLS_SERVER_CERT": str(certificates / "server.crt"),
        "REFLEXGUARD_TLS_SERVER_KEY": str(certificates / "server.key"),
        "REFLEXGUARD_BRAIN_PORT": "18444",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return directory


def test_local_server_is_signed_numpy_on_loopback_with_required_client_certificate(settings):
    config = local.configuration()
    assert config.host == "127.0.0.1"
    assert config.ssl.verify_mode == ssl.CERT_REQUIRED
    assert config.ssl.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert config.app.state.simulation.circuit.backend == "numpy"
    assert config.app.state.simulation.circuit.manifest.model_version.startswith("malecns-")
    config.app.state.simulation.close()


def test_tampered_local_assets_prevent_startup(settings):
    path = settings / "assets.lock"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises((ValueError, InvalidSignature)):
        local.configuration()
