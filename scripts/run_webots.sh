#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $# -le 1 ]] || exit 2
world=${1:-corridor_basic}
case "$world" in corridor_basic|corridor_side|corridor_static) ;; *) printf 'Unknown world ID\n' >&2; exit 2 ;; esac
source scripts/brain_profile.sh
if [[ -f .env.control ]]; then set -a; source .env.control; set +a; fi
unset REFLEXGUARD_SCENARIO
.venv/bin/python scripts/configure_webots.py
exec webots "$PWD/webots/worlds/$world.wbt"
