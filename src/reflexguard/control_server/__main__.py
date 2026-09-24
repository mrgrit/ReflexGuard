"""Loopback-only HTTPS dashboard. Brain traffic remains separately protected by mTLS."""
import logging
import os
import ssl
import uvicorn
from pydantic import Field, TypeAdapter
from typing import Annotated
from reflexguard.common.config import ServerTLSSettings
from reflexguard.control_server.app import create_app

def main():
    logging.basicConfig(level=logging.INFO)
    os.umask(0o077)
    tls=ServerTLSSettings.from_env()
    port=TypeAdapter(Annotated[int,Field(ge=1024,le=65535)]).validate_python(os.environ.get("REFLEXGUARD_CONTROL_PORT","8444"))
    config=uvicorn.Config(create_app(),host="127.0.0.1",port=port,
        ssl_certfile=str(tls.server_cert),ssl_keyfile=str(tls.server_key),ssl_version=ssl.PROTOCOL_TLS_SERVER,
        proxy_headers=False,server_header=False,access_log=False,limit_concurrency=32,backlog=32,timeout_keep_alive=2)
    config.load()
    if config.ssl is None:
        raise RuntimeError("HTTPS required")
    config.ssl.minimum_version=ssl.TLSVersion.TLSv1_2
    uvicorn.Server(config).run()

if __name__=="__main__":
    main()
