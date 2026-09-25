"""Production launcher: mandatory trusted model key, CUDA and mutual TLS."""
import base64
import logging
import os
from pathlib import Path
import ssl
import socket
from ipaddress import IPv4Address
from pydantic import TypeAdapter
import uvicorn

from reflexguard.common.config import MockSettings, ServerTLSSettings
from reflexguard.common.schemas import StepRequest
from brain_server.app import create_app
from brain_server.loader import load_assets
from brain_server.model import Circuit
import time


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        public_key = base64.b64decode(os.environ['REFLEXGUARD_MODEL_PUBLIC_KEY'], validate=True)
        circuit = Circuit(load_assets(Path(os.environ['REFLEXGUARD_MODEL_DIR']), public_key), backend='cuda')
        # Compile/initialize kernels before reporting readiness; discard warm-up state.
        circuit.step(circuit.state(), StepRequest(t_ms=0, dt_ms=50, left_looming=0.5, right_looming=0.5), set(), time.monotonic() + 30.)
        settings = MockSettings.from_env()
        tls = ServerTLSSettings.model_validate({
            'ca_cert': os.environ.get('REFLEXGUARD_TLS_CA'),
            'server_cert': os.environ.get('REFLEXGUARD_TLS_SERVER_CERT'),
            'server_key': os.environ.get('REFLEXGUARD_TLS_SERVER_KEY'),
            'port': os.environ.get('REFLEXGUARD_BRAIN_PORT', '8443'),
        })
        bind_address = TypeAdapter(IPv4Address).validate_python(socket.gethostbyname(socket.gethostname()))
        if not bind_address.is_private or bind_address.is_unspecified or bind_address.is_multicast:
            raise ValueError('A specific private container address is required')
    except Exception as exc:
        logging.error('Brain initialization rejected (%s)', type(exc).__name__)
        raise SystemExit(1) from None
    config = uvicorn.Config(
        create_app(settings, circuit), host=str(bind_address), port=tls.port,
        ssl_keyfile=str(tls.server_key), ssl_certfile=str(tls.server_cert),
        ssl_ca_certs=str(tls.ca_cert), ssl_cert_reqs=ssl.CERT_REQUIRED,
        ssl_version=ssl.PROTOCOL_TLS_SERVER, proxy_headers=False, server_header=False,
        access_log=False, limit_concurrency=16, backlog=16, timeout_keep_alive=5,
    )
    config.load()
    if config.ssl is None:
        raise RuntimeError('TLS is required')
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    uvicorn.Server(config).run()


if __name__ == '__main__':
    main()
