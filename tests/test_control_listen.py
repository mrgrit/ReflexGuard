"""Listen-address validation and canonical-origin protection for LAN access."""
import ssl
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from reflexguard.control_server import __main__ as entry


@pytest.mark.parametrize("host", [None, "0.0.0.0", "127.0.0.1", "::"])
def test_server_binding_keeps_https_and_disables_proxy_headers(monkeypatch, certificates, host):
    captured = {}
    if host is None:
        monkeypatch.delenv("REFLEXGUARD_CONTROL_HOST", raising=False)
    else:
        monkeypatch.setenv("REFLEXGUARD_CONTROL_HOST", host)
    monkeypatch.setattr(entry.ServerTLSSettings, "from_env", lambda: SimpleNamespace(
        server_cert=certificates / "server.crt", server_key=certificates / "server.key"))
    monkeypatch.setattr(entry, "create_app", lambda: object())

    class Server:
        def __init__(self, config):
            captured["config"] = config

        def run(self):
            pass

    monkeypatch.setattr(entry.uvicorn, "Server", Server)
    entry.main()
    config = captured["config"]
    assert config.host == (host or "127.0.0.1")
    assert config.ssl.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert not config.proxy_headers


def test_invalid_listen_address_rejected_before_app_initialization(monkeypatch):
    monkeypatch.setenv("REFLEXGUARD_CONTROL_HOST", "https://0.0.0.0:8444")
    monkeypatch.setattr(entry.ServerTLSSettings, "from_env", lambda: None)
    monkeypatch.setattr(entry, "create_app", lambda: pytest.fail("must validate binding first"))
    with pytest.raises(ValidationError):
        entry.main()
