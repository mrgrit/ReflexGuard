#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$root"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
if [[ -f .env.control ]]; then set -a; source .env.control; set +a; fi
# A public dashboard certificate must not replace the brain's mTLS credentials.
if [[ -n ${REFLEXGUARD_CONTROL_TLS_CERT:-} ]]; then export REFLEXGUARD_TLS_SERVER_CERT="$REFLEXGUARD_CONTROL_TLS_CERT"; fi
if [[ -n ${REFLEXGUARD_CONTROL_TLS_KEY:-} ]]; then export REFLEXGUARD_TLS_SERVER_KEY="$REFLEXGUARD_CONTROL_TLS_KEY"; fi
export PYTHONPATH="$root/src"
exec "$root/.venv/bin/python" -m reflexguard.control_server
