#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ${REFLEXGUARD_BRAIN_PROFILE:-mock} == real ]]; then source scripts/brain_profile.sh; fi
export PYTHONPATH="$PWD/src"
exec .venv/bin/python scripts/check_control.py
