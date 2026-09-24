#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$root"
export PYTHONPATH="$root/src"
exec "$root/.venv/bin/python" -m reflexguard.mock_brain
