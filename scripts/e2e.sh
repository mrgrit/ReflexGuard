#!/usr/bin/env bash
# Test-owned mock, or preconfigured real GPU over its authenticated SSH tunnel.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $# == 1 && ( $1 == mock || $1 == real ) ]] || { printf 'Usage: scripts/e2e.sh mock|real\n' >&2; exit 2; }
export REFLEXGUARD_BRAIN_PROFILE="$1"
source scripts/brain_profile.sh
export PYTHONPATH="$PWD/src:$PWD"
log_dir=$(mktemp -d /tmp/reflexguard-e2e-XXXXXXXX)
printf 'Integration evidence: %s\n' "$log_dir" >&2
server_pid=''
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT
if [[ $REFLEXGUARD_BRAIN_PROFILE == mock ]]; then
  scripts/run_mock_brain.sh >"$log_dir/server.log" 2>&1 &
  server_pid=$!
  ready=false
  for attempt in {1..30}; do
    kill -0 "$server_pid" || { cat "$log_dir/server.log" >&2; exit 1; }
    if scripts/smoke_brain.sh >"$log_dir/health.log" 2>&1; then ready=true; break; fi
    sleep 0.2
  done
  "$ready" || exit 1
  sleep 0.2
  kill -0 "$server_pid"
else
  .venv/bin/python scripts/check_real_brain.py >"$log_dir/contract.json"
fi
for world in corridor_basic corridor_side corridor_static; do
  scripts/run_scenario.sh "$world" 10 forward >"$log_dir/$world.json" 2>"$log_dir/$world.log"
  .venv/bin/python -m reflexguard.simulation.verify <"$log_dir/$world.json"
done
scripts/run_scenario.sh corridor_static 3 idle >"$log_dir/idle.json" 2>"$log_dir/idle.log"
.venv/bin/python -m reflexguard.simulation.verify <"$log_dir/idle.json"
.venv/bin/python scripts/check_disconnect.py >"$log_dir/disconnect.json"
scripts/check_control.sh >"$log_dir/control.json" 2>"$log_dir/control.log"
.venv/bin/python scripts/e2e_report.py "$log_dir" "$REFLEXGUARD_BRAIN_PROFILE"
