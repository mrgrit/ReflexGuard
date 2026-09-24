#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ $# -lt 1 || $# -gt 3 ]]; then
  printf 'Usage: run_scenario.sh corridor_basic|corridor_side|corridor_static [seconds:1..60] [forward|idle|reverse|left|right]\n' >&2
  exit 2
fi
case "$1" in corridor_basic|corridor_side|corridor_static) world=$1 ;; *) printf 'Unknown world ID\n' >&2; exit 2 ;; esac
seconds=${2:-10}
drive=${3:-forward}
[[ "$seconds" =~ ^([1-9]|[1-5][0-9]|60)$ ]] || { printf 'Invalid duration\n' >&2; exit 2; }
case "$drive" in forward|idle|reverse|left|right) ;; *) printf 'Unknown drive input\n' >&2; exit 2 ;; esac
.venv/bin/python scripts/configure_webots.py
export PYTHONPATH="$PWD/src"
REFLEXGUARD_SCENARIO=$(.venv/bin/python -m reflexguard.simulation.runner settings "$world" "$seconds" "$drive")
export REFLEXGUARD_SCENARIO
log_dir=$(mktemp -d)
trap 'rm -rf -- "$log_dir"' EXIT
status=0
timeout --signal=TERM --kill-after=5s 180s xvfb-run -a webots   --batch --mode=fast --no-rendering --minimize --stdout --stderr   "$PWD/webots/worlds/$world.wbt" >"$log_dir/webots.log" 2>&1 || status=$?
cat -- "$log_dir/webots.log" >&2
if [[ $status -ne 0 ]]; then
  printf 'Scenario failed or timed out (exit %s)\n' "$status" >&2
  exit 1
fi
.venv/bin/python -m reflexguard.simulation.runner result <"$log_dir/webots.log"
