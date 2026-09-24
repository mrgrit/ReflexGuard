#!/usr/bin/env bash
# Starts a local mTLS mock only for this bounded simulation check.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] || { printf 'Configure .env and certificates first.\n' >&2; exit 1; }
set -a
source .env
set +a
log_dir=$(mktemp -d)
server_pid=''
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  cat "$log_dir/server.log" >&2
  rm -rf -- "$log_dir"
}
trap cleanup EXIT
scripts/run_mock_brain.sh >"$log_dir/server.log" 2>&1 &
server_pid=$!
ready=false
for attempt in {1..30}; do
  kill -0 "$server_pid" 2>/dev/null || { printf 'Test mock did not start.\n' >&2; exit 1; }
  if scripts/smoke_brain.sh >"$log_dir/health.log" 2>&1; then
    ready=true
    break
  fi
  sleep 0.2
done
"$ready" || { printf 'Test mock was not ready.\n' >&2; exit 1; }
# Ensure the successful health reply was from this newly started process.
sleep 0.2
kill -0 "$server_pid"
run_check() {
  scripts/run_scenario.sh "$@" | tee "$log_dir/result.json"
  PYTHONPATH=src .venv/bin/python -m reflexguard.simulation.verify <"$log_dir/result.json"
}
if [[ $# -gt 0 ]]; then
  run_check "$@"
else
  for world in corridor_basic corridor_side corridor_static; do
    run_check "$world" 10
  done
  run_check corridor_static 3 idle
fi
