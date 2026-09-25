#!/usr/bin/env bash
# Run on the prepared GPU host. Reach its private container IP through SSH.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $# == 0 ]] || exit 2
model_dir="$HOME/work/reflexguard-models/malecns-v1-lif-v1"
secret_dir="$HOME/work/reflexguard-secrets/brain"
[[ -f "$model_dir/assets.lock.sig" && -f "$model_dir/silence.json.sig" && -f "$secret_dir/server.env" ]] || {
  printf 'Signed assets and dedicated TLS/credential configuration are required.\n' >&2; exit 2;
}
if docker container inspect reflexguard-brain >/dev/null 2>&1; then
  printf 'reflexguard-brain already exists; inspect and stop the previous deployment before replacing it.\n' >&2
  exit 2
fi
if ! docker network inspect reflexguard-brain >/dev/null 2>&1; then
  docker network create --internal reflexguard-brain >/dev/null
fi
[[ $(docker network inspect --format '{{.Internal}}' reflexguard-brain) == true ]] || exit 2
image=$(docker image inspect --format '{{.Id}}' reflexguard-brain:phase6)
docker run --detach --name reflexguard-brain --runtime=nvidia --gpus all \
  --network reflexguard-brain --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 8g --cpus 4 --shm-size 256m \
  --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --env-file "$secret_dir/server.env" \
  --mount "type=bind,src=$model_dir,dst=/model,readonly" \
  --mount "type=bind,src=$secret_dir,dst=/run/reflexguard,readonly" "$image"
