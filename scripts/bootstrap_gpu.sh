#!/usr/bin/env bash
# GPU environment only. JetPack supplies the host CUDA driver/runtime.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
image='nvcr.io/nvidia/pytorch@sha256:d724ba5b68075cd3b96eefbc510a45d36e60dd16fd70b217708625f1f4b37bc1'
if [[ ${1:-} == --help ]]; then
  printf 'Usage: bash scripts/bootstrap_gpu.sh [--dry-run]\nRequires Ubuntu 24.04 ARM64, JetPack 7.1, Docker and NVIDIA Container Toolkit.\nPulls the pinned NVIDIA image and runs isolated CUDA arithmetic checks.\n'
  exit 0
fi
if [[ ${1:-} == --dry-run && $# == 1 ]]; then
  printf 'Image: %s\nScope: GPU environment, not the MaleCNS API server.\nLimits: 4 CPUs, 8 GiB, 256 processes, no network, no host ports.\n' "$image"
  exit 0
fi
[[ $# == 0 ]] || { printf 'Unknown arguments\n' >&2; exit 2; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && $(uname -m) == aarch64 ]] || {
  printf 'Requires Ubuntu 24.04 aarch64 with JetPack 7.1.\n' >&2; exit 2;
}
[[ -r /etc/nv_tegra_release ]] && grep -q '^# R38 .*REVISION: 4.0' /etc/nv_tegra_release || {
  printf 'This environment was validated with Jetson Linux R38.4 / JetPack 7.1.\n' >&2; exit 2;
}
command -v docker >/dev/null
docker info --format '{{json .Runtimes}}' | python3 -c 'import json,sys; sys.exit(0 if "nvidia" in json.load(sys.stdin) else 1)'
docker pull --platform linux/arm64 "$image"
docker run --rm --runtime=nvidia --gpus all --network none \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 256 --memory 8g --cpus 4 --shm-size 256m \
  --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$PWD/scripts/check_gpu.py,dst=/check_gpu.py,readonly" \
  --entrypoint python3 "$image" /check_gpu.py
