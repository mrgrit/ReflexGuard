"""Only supported mock server entry point: mandatory mTLS, loopback binding."""

import logging
import ssl

import uvicorn

from reflexguard.common.config import MockSettings, ServerTLSSettings
from reflexguard.mock_brain.app import create_app


def main():
    logging.basicConfig(level=logging.INFO)
    settings = MockSettings.from_env()
    tls = ServerTLSSettings.from_env()
    config = uvicorn.Config(
        create_app(settings), host="127.0.0.1", port=tls.port,
        ssl_keyfile=str(tls.server_key), ssl_certfile=str(tls.server_cert),
        ssl_ca_certs=str(tls.ca_cert), ssl_cert_reqs=ssl.CERT_REQUIRED,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        proxy_headers=False, server_header=False, access_log=False,
        limit_concurrency=32, backlog=32, timeout_keep_alive=5,
    )
    config.load()
    if config.ssl is None:
        raise RuntimeError("TLS configuration is required")
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
