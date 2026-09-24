"""Real loopback TCP/TLS tests; ASGI-only tests cannot prove mTLS enforcement."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import time

import httpx
import pytest

from reflexguard.brain_client.client import BrainClient
from reflexguard.common.config import ClientSettings
from reflexguard.common.schemas import StepRequest

ROOT = Path(__file__).resolve().parents[1]


def tls_context(certs, client_certs=None):
    context = ssl.create_default_context(cafile=str(certs / "ca.crt"))
    if client_certs is not None:
        context.load_cert_chain(str(client_certs / "client.crt"), str(client_certs / "client.key"))
    return context


@pytest.fixture(scope="module")
def live_server(certificates, tmp_path_factory):
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
    token = secrets.token_urlsafe(32)
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "REFLEXGUARD_API_TOKENS": json.dumps([{"token": token, "subject": "integration", "role": "operator"}]),
        "REFLEXGUARD_BRAIN_TOKEN": token,
        "REFLEXGUARD_BRAIN_URL": f"https://localhost:{port}",
        "REFLEXGUARD_MOCK_PORT": str(port),
        "REFLEXGUARD_TLS_CA": str(certificates / "ca.crt"),
        "REFLEXGUARD_TLS_SERVER_CERT": str(certificates / "server.crt"),
        "REFLEXGUARD_TLS_SERVER_KEY": str(certificates / "server.key"),
        "REFLEXGUARD_TLS_CLIENT_CERT": str(certificates / "client.crt"),
        "REFLEXGUARD_TLS_CLIENT_KEY": str(certificates / "client.key"),
    }
    logfile = tmp_path_factory.mktemp("server") / "server.log"
    with logfile.open("w") as log:
        process = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "reflexguard.mock_brain"],
            env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(verify=tls_context(certificates, certificates), trust_env=False, timeout=0.2) as probe:
                deadline = time.monotonic() + 10
                while True:
                    if process.poll() is not None:
                        pytest.fail("TLS server startup failed: " + logfile.read_text())
                    try:
                        ready = probe.get(env["REFLEXGUARD_BRAIN_URL"] + "/v1/health",
                                          headers={"Authorization": "Bearer " + token})
                        if ready.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        pytest.fail("TLS server did not become ready: " + logfile.read_text())
                    time.sleep(0.03)
            yield {"url": env["REFLEXGUARD_BRAIN_URL"], "port": port, "token": token, "env": env}
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_real_mtls_client_step_silence_and_health(live_server, certificates):
    settings = ClientSettings(
        base_url=live_server["url"], token=live_server["token"],
        ca_cert=certificates / "ca.crt", client_cert=certificates / "client.crt",
        client_key=certificates / "client.key",
    )

    async def run():
        async with BrainClient(settings) as client:
            assert (await client.health()).status == "ok"
            session = await client.create_session()
            first = await client.step(session.session_id, StepRequest(
                t_ms=0, dt_ms=50, left_looming=0.9, right_looming=0.1,
            ))
            assert first.escape > 0
            assert first.turn_right > first.turn_left
            silence = await client.silence(session.session_id, ["mock-escape"])
            assert silence.accepted == ["mock-escape"]
            second = await client.step(session.session_id, StepRequest(
                t_ms=50, dt_ms=50, left_looming=0.9, right_looming=0.1,
            ))
            assert second.escape == 0

    asyncio.run(run())


def test_missing_client_certificate_is_rejected(live_server, certificates):
    with httpx.Client(verify=tls_context(certificates), trust_env=False, timeout=2) as client:
        with pytest.raises(httpx.TransportError):
            client.get(live_server["url"] + "/v1/health",
                       headers={"Authorization": "Bearer " + live_server["token"]})


def test_foreign_client_certificate_is_rejected(live_server, certificates, untrusted_certificates):
    with httpx.Client(verify=tls_context(certificates, untrusted_certificates), trust_env=False, timeout=2) as client:
        with pytest.raises(httpx.TransportError):
            client.get(live_server["url"] + "/v1/health",
                       headers={"Authorization": "Bearer " + live_server["token"]})


def test_foreign_server_ca_is_rejected(live_server, certificates, untrusted_certificates):
    with httpx.Client(verify=tls_context(untrusted_certificates, certificates), trust_env=False, timeout=2) as client:
        with pytest.raises(httpx.TransportError):
            client.get(live_server["url"] + "/v1/health")


def test_hostname_verification_is_enabled(live_server, certificates):
    context = tls_context(certificates, certificates)
    with socket.create_connection(("127.0.0.1", live_server["port"]), timeout=2) as raw:
        with pytest.raises(ssl.SSLCertVerificationError):
            context.wrap_socket(raw, server_hostname="not-localhost.invalid")


def test_mtls_does_not_replace_bearer_auth(live_server, certificates):
    with httpx.Client(verify=tls_context(certificates, certificates), trust_env=False, timeout=2) as client:
        assert client.get(live_server["url"] + "/v1/health").status_code == 401


def test_plaintext_and_forged_forwarded_proto_are_rejected(live_server):
    with httpx.Client(trust_env=False, timeout=2) as client:
        with pytest.raises(httpx.TransportError):
            client.get(f"http://127.0.0.1:{live_server['port']}/v1/health",
                       headers={"X-Forwarded-Proto": "https"})


def test_smoke_command_uses_the_same_client(live_server):
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "scripts/smoke_brain.sh")],
        cwd=ROOT, env=live_server["env"], check=True, capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    assert data["health"]["status"] == "ok"
    assert data["step"]["turn_right"] > 0
    assert live_server["token"] not in result.stdout + result.stderr


def test_private_keys_are_restricted_and_never_overwritten(certificates):
    before = (certificates / "ca.key").read_bytes()
    for name in ("ca", "server", "client"):
        assert (certificates / f"{name}.key").stat().st_mode & 0o777 == 0o600
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "scripts/gen_certs.sh"), str(certificates)],
        check=False, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert (certificates / "ca.key").read_bytes() == before
