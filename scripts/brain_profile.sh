#!/usr/bin/env bash
# Sourced from repository-root launchers. Profiles map to fixed local files.
case "${REFLEXGUARD_BRAIN_PROFILE:-mock}" in
  mock)
    if [[ -f .env ]]; then set -a; source .env; set +a; fi
    ;;
  real|local)
    [[ -f .env.brain-client ]] || { printf 'Missing real-brain client configuration\n' >&2; exit 2; }
    if [[ -f .env ]]; then set -a; source .env; set +a; fi
    if [[ -n ${REFLEXGUARD_TLS_CA:-} ]]; then export REFLEXGUARD_CONTROL_TLS_CA="$REFLEXGUARD_TLS_CA"; fi
    set -a
    source .env.brain-client
    if [[ $REFLEXGUARD_BRAIN_PROFILE == local ]]; then
      [[ -f .env.local-client ]] || { printf 'Missing local MaleCNS client configuration\n' >&2; exit 2; }
      source .env.local-client
    fi
    set +a
    ;;
  *) printf 'Unknown brain profile\n' >&2; exit 2 ;;
esac
