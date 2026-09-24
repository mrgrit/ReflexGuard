#!/usr/bin/env bash
set -euo pipefail
log_dir=${1:-"$HOME/.cache/reflexguard-bootstrap/logs"}
mkdir -p -- "$log_dir"
world=/usr/local/webots/projects/samples/howto/console/worlds/console.wbt
[[ -r "$world" ]] || { printf 'Webots console sample is missing.\n' >&2; exit 1; }

# The official sample advances 4096 ms and exits its controller. Webots itself
# stays open, so timeout 124 is expected only AFTER controller success appears.
status=0
timeout --signal=TERM --kill-after=5s 30s \
  xvfb-run -a webots --batch --mode=fast --no-rendering --minimize \
  --stdout --stderr "$world" > "$log_dir/webots-sample.log" 2>&1 || status=$?
if [[ $status -ne 0 && $status -ne 124 ]]; then
  cat -- "$log_dir/webots-sample.log"
  exit 1
fi
if ! grep -Fq "INFO: 'console' controller exited successfully." "$log_dir/webots-sample.log"; then
  cat -- "$log_dir/webots-sample.log"
  printf 'Webots did not complete the sample controller.\n' >&2
  exit 1
fi
if grep -Eq '^(ERROR:|FATAL:|Fatal:)' "$log_dir/webots-sample.log"; then
  cat -- "$log_dir/webots-sample.log"
  exit 1
fi
printf 'Webots sample PASS: controller completed after 4096 ms of simulation (process exit %s).\n' "$status"
