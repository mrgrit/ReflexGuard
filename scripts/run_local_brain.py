"""Explicit local MaleCNS simulation with the same signed assets and mTLS API."""
import base64
import logging
import os
from pathlib import Path
import ssl
import time

import uvicorn

from brain_server.app import create_app
from brain_server.loader import load_assets
from brain_server.model import Circuit
from reflexguard.common.config import MockSettings, ServerTLSSettings
from reflexguard.common.schemas import StepRequest


def configuration():
    public_key = base64.b64decode(os.environ["REFLEXGUARD_MODEL_PUBLIC_KEY"], validate=True)
    circuit = Circuit(load_assets(Path(os.environ["REFLEXGUARD_MODEL_DIR"]), public_key), backend="numpy")
    circuit.step(circuit.state(), StepRequest(t_ms=0, dt_ms=50, left_looming=.5, right_looming=.5),
                 set(), time.monotonic() + .15)
    tls = ServerTLSSettings.model_validate({
        "ca_cert": os.environ.get("REFLEXGUARD_TLS_CA"),
        "server_cert": os.environ.get("REFLEXGUARD_TLS_SERVER_CERT"),
        "server_key": os.environ.get("REFLEXGUARD_TLS_SERVER_KEY"),
        "port": os.environ.get("REFLEXGUARD_BRAIN_PORT", "18444"),
    })
    config = uvicorn.Config(
        create_app(MockSettings.from_env(), circuit), host="127.0.0.1", port=tls.port,
        ssl_keyfile=str(tls.server_key), ssl_certfile=str(tls.server_cert),
        ssl_ca_certs=str(tls.ca_cert), ssl_cert_reqs=ssl.CERT_REQUIRED,
        ssl_version=ssl.PROTOCOL_TLS_SERVER, proxy_headers=False, server_header=False,
        access_log=False, limit_concurrency=16, backlog=16, timeout_keep_alive=5,
    )
    config.load()
    if config.ssl is None:
        raise ValueError("TLS is required")
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    return config


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        config = configuration()
    except Exception as exc:
        logging.error("Local brain initialization rejected (%s)", type(exc).__name__)
        raise SystemExit(1) from None
    logging.info("MaleCNS signed LIF circuit / LOCAL CPU / no mock fallback")
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
