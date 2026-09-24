#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$root"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
if [[ -f .env.control ]]; then set -a; source .env.control; set +a; fi
export PYTHONPATH="$root/src"
exec "$root/.venv/bin/python" -m reflexguard.control_server
