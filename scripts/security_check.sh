#!/usr/bin/env bash
set -euo pipefail
trap 'exit 1' ERR
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PWD/.venv/bin:$PATH"
targets=(scripts)
for directory in src brain_server webots/controllers; do
  if [[ -d "$directory" ]]; then
    targets+=("$directory")
  fi
done
bandit -r "${targets[@]}"
semgrep scan --config p/python --error --metrics=off .
pip-audit --require-hashes -r requirements.txt
.venv/bin/python -m pytest
