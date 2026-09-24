#!/usr/bin/env bash
# Ubuntu 22.04 amd64 host setup. Run as the normal desktop/SSH user.
set -euo pipefail
trap 'printf "Bootstrap failed at line %s. Fix the reported error and rerun.\n" "$LINENO" >&2' ERR

usage() {
  cat <<'EOF'
Usage: bash bootstrap.sh [--dry-run] [--prefix /absolute/repository/path]

Install ReflexGuard's Ubuntu 22.04 amd64 development environment:
  base build/Python tools, Xvfb, Docker Engine/Compose, Webots R2025a,
  hash-locked pipx security tools, project .venv, and Korean input support.
Then run Docker/Webots smoke checks and the repository security gate.

Run as a normal user with sudo privileges; sudo asks for your password locally.
Default repository: this checkout, or ~/work/reflexguard when downloaded alone.
--dry-run shows the plan without sudo, network access, or filesystem changes.
Existing repository work is preserved; no automatic pull, commit, or push.
EOF
}

prefix=''
dry_run=false
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --dry-run) dry_run=true; shift ;;
    --prefix)
      [[ $# -ge 2 && -n "$2" ]] || { printf 'Missing --prefix value\n' >&2; exit 2; }
      prefix=$2; shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -z "$prefix" ]]; then
  if [[ -f "$script_dir/../tools/locks/bandit.txt" && -f "$script_dir/../AGENTS.md" ]]; then
    prefix=$(cd -- "$script_dir/.." && pwd)
  else
    prefix="$HOME/work/reflexguard"
  fi
fi
[[ "$prefix" == /* && "$prefix" != / && "$prefix" != "$HOME" && "$prefix" != *$'\n'* ]] || {
  printf 'Choose an absolute repository directory, not / or your home directory.\n' >&2
  exit 2
}
prefix=$(realpath -m -- "$prefix")
[[ "$prefix" != / && "$prefix" != "$HOME" ]] || {
  printf 'Repository path resolves to / or your home directory.\n' >&2; exit 2
}

if "$dry_run"; then
  usage
  printf '\nRepository: %s\nWebots: R2025a, SHA-256 verified\n' "$prefix"
  printf 'Python tools: version/hash-locked files in tools/locks/\n'
  printf 'Checks: Docker hello-world, Webots batch simulation, Bandit, Semgrep, pip-audit, pytest\n'
  exit 0
fi

[[ $EUID -ne 0 ]] || { printf 'Run as your normal user, without sudo bash.\n' >&2; exit 2; }
# This is an OS-owned configuration file, never a downloaded shell fragment.
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 22.04 && $(uname -m) == x86_64 ]] || {
  printf 'This script supports Ubuntu 22.04 x86_64 only.\n' >&2; exit 2
}
[[ ! -e "$prefix" || -d "$prefix/.git" ]] || {
  printf 'Destination exists but is not a Git checkout: %s\n' "$prefix" >&2; exit 2
}
command -v sudo >/dev/null
sudo -v
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git curl ca-certificates build-essential python3-venv python3-pip pipx \
  xvfb xauth mesa-utils ibus-hangul python3-gi

repository_url=https://github.com/mrgrit/reflexguard.git
if [[ ! -d "$prefix/.git" ]]; then
  mkdir -p -- "$(dirname -- "$prefix")"
  git clone "$repository_url" "$prefix"
fi
cd -- "$prefix"
origin=$(git remote get-url origin)
case "${origin,,}" in
  https://github.com/mrgrit/reflexguard|https://github.com/mrgrit/reflexguard.git|git@github.com:mrgrit/reflexguard.git) ;;
  *) printf 'Destination has a different Git origin; leaving it unchanged.\n' >&2; exit 2 ;;
esac
[[ -f requirements.txt && -f tools/locks/bandit.txt && -f scripts/security_check.sh ]] || {
  printf 'Required lock files are missing; use a complete ReflexGuard checkout.\n' >&2; exit 2
}

for package in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
  if [[ $(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true) == installed ]]; then
    printf 'Conflicting package %s is installed; resolve it before rerunning.\n' "$package" >&2
    exit 2
  fi
done
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl --proto '=https' --tlsv1.2 -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod 0644 /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: jammy
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$(id -un)"
sudo systemctl enable --now docker

webots_version=2025a
webots_sha256=6253d58c9b625a83ed7b62cd85a640fd0542d441c48d633a60932208b40b0657
cache_dir="$HOME/.cache/reflexguard-bootstrap"
mkdir -p -- "$cache_dir"
webots_deb="$cache_dir/webots_2025a_amd64.deb"
if [[ $(dpkg-query -W -f='${Version}' webots 2>/dev/null || true) != "$webots_version" ]]; then
  curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fL --retry 3 \
    https://github.com/cyberbotics/webots/releases/download/R2025a/webots_2025a_amd64.deb \
    -o "$webots_deb"
  printf '%s  %s\n' "$webots_sha256" "$webots_deb" | sha256sum --check --status
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "$webots_deb"
fi

export PATH="$HOME/.local/bin:$PATH"
pipx ensurepath
for package in bandit semgrep pip-audit pre-commit cyclonedx-bom pip-tools; do
  lock="$prefix/tools/locks/$package.txt"
  spec=$(cat -- "$prefix/tools/locks/$package.in")
  [[ "$spec" =~ ^[a-z][a-z0-9-]*==[0-9][a-zA-Z0-9.]*$ && -s "$lock" ]] || {
    printf 'Invalid tool lock: %s\n' "$package" >&2; exit 2
  }
  # Reapply the lock on every run, including transitive dependencies.
  pip_args=$(python3 -c 'import shlex, sys; print(shlex.join(["--require-hashes", "--requirement", sys.argv[1]]))' "$lock")
  pipx install --force --python /usr/bin/python3 --pip-args="$pip_args" "$spec"
done
if [[ ! -x .venv/bin/python ]]; then
  /usr/bin/python3 -m venv .venv
fi
.venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 10) and sys.prefix != sys.base_prefix else 1)'
.venv/bin/python -m pip install --require-hashes -r requirements.txt
pre-commit install

# Do not restart the desktop's input daemon or log the user out automatically.
if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && command -v gsettings >/dev/null; then
  /usr/bin/python3 scripts/configure_korean.py
fi

log_dir="$cache_dir/logs"
mkdir -p -- "$log_dir"
sg docker -c 'docker run --rm hello-world' | tee "$log_dir/docker.log"
xvfb-run -a webots --version | tee "$log_dir/webots-version.log"
scripts/check_webots.sh "$log_dir"
scripts/security_check.sh 2>&1 | tee "$log_dir/security.log"
printf '\nCompleted: %s\nLogs: %s\n' "$prefix" "$log_dir"
printf 'Log out and back in to activate Docker group membership and Korean input.\n'
printf 'Select Korean with Super+Space. VMware 3D acceleration must be enabled on the host.\n'
