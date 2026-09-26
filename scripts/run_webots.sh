#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $# -le 1 ]] || exit 2
world=${1:-corridor_demo}
case "$world" in corridor_basic|corridor_side|corridor_static|corridor_demo) ;; *) printf 'Unknown world ID\n' >&2; exit 2 ;; esac
export REFLEXGUARD_BRAIN_PROFILE="${REFLEXGUARD_BRAIN_PROFILE:-local}"
source scripts/brain_profile.sh
if [[ -f .env.control ]]; then set -a; source .env.control; set +a; fi
unset REFLEXGUARD_SCENARIO
export PYTHONPATH="$PWD/src:$PWD"
if ! .venv/bin/python scripts/check_brain_ready.py; then
  if [[ ${REFLEXGUARD_BRAIN_PROFILE:-mock} == real || ${REFLEXGUARD_BRAIN_PROFILE:-mock} == local ]]; then
    service=reflexguard-gpu-tunnel.service
    if [[ $REFLEXGUARD_BRAIN_PROFILE == local ]]; then service=reflexguard-local-brain.service; fi
    printf 'MaleCNS 연결 복구 중: %s\n' "$service" >&2
    if ! systemctl --user start "$service"; then
      printf '뇌 연결 서비스를 시작하지 못했습니다. 선택한 프로필의 서비스 설정을 확인하세요.\n' >&2
      exit 1
    fi
    ready=false
    for attempt in {1..10}; do
      if .venv/bin/python scripts/check_brain_ready.py; then ready=true; break; fi
      sleep 0.5
    done
    if ! "$ready"; then
      printf '뇌 응답을 확인하지 못해 Webots 실행을 중단합니다. 선택한 프로필의 서비스 상태를 확인하세요.\n' >&2
      exit 1
    fi
  else
    printf 'mock 뇌 서버를 먼저 실행하세요: scripts/run_mock_brain.sh\n' >&2
    exit 1
  fi
fi
.venv/bin/python scripts/configure_webots.py
exec webots "$PWD/webots/worlds/$world.wbt"
