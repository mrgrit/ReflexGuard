#!/usr/bin/env bash
# VPN must already be connected. Local connection settings contain no password.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $# == 0 && -f .env.gpu ]] || { printf 'Configure .env.gpu as described in docs/phase6.md.\n' >&2; exit 2; }
source .env.gpu
[[ ${REFLEXGUARD_GPU_HOST:-} =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || exit 2
[[ ${REFLEXGUARD_GPU_USER:-} =~ ^[a-z_][a-z0-9_-]*$ ]] || exit 2
[[ ${REFLEXGUARD_GPU_PORT:-} =~ ^[0-9]{1,5}$ ]] || exit 2
(( 10#$REFLEXGUARD_GPU_PORT >= 1 && 10#$REFLEXGUARD_GPU_PORT <= 65535 )) || exit 2
target="$REFLEXGUARD_GPU_USER@$REFLEXGUARD_GPU_HOST"
ssh_options=(-p "$REFLEXGUARD_GPU_PORT" -o ConnectTimeout=10 -o ControlPath=/tmp/rg-thor-%C)
key="$HOME/.ssh/reflexguard_gpu_ed25519"
if [[ -f "$key" ]]; then
  # Dedicated service key; no dependency on a temporary multiplexed SSH master.
  ssh_options=(-p "$REFLEXGUARD_GPU_PORT" -o ConnectTimeout=10 -o ControlPath=none
    -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -i "$key")
fi
address=$(ssh "${ssh_options[@]}" "$target" "docker inspect --format '{{with index .NetworkSettings.Networks \"reflexguard-brain\"}}{{.IPAddress}}{{end}}' reflexguard-brain")
[[ $address =~ ^172\.([0-9]{1,3}\.){2}[0-9]{1,3}$ || $address =~ ^10\.([0-9]{1,3}\.){2}[0-9]{1,3}$ || $address =~ ^192\.168\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || exit 2
printf 'Authenticated brain tunnel: https://localhost:18443 (foreground process; managed by systemd when installed)\n' >&2
exec ssh "${ssh_options[@]}" -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -N -L "127.0.0.1:18443:$address:8443" "$target"
