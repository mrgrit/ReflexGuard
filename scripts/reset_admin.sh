#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
set -a
source .env.control
set +a
export PYTHONPATH="$PWD/src"
exec .venv/bin/python -m reflexguard.control_server.reset_admin
