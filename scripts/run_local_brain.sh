#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $# == 0 && -f .env.local-brain ]] || { printf 'Configure .env.local-brain first.\n' >&2; exit 2; }
set -a
source .env.local-brain
set +a
export PYTHONPATH="$PWD/src:$PWD"
exec .venv/bin/python scripts/run_local_brain.py
