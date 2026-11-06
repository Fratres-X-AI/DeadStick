#!/usr/bin/env bash
# [HEAVY] Run on RunPod CPU only — builds ArduCopter SITL and writes ardupilot.lock
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AP_DIR="${ROOT}/ardupilot"
LOCK="${ROOT}/ardupilot.lock"

cd "$ROOT"

if [ ! -d "$AP_DIR" ]; then
  # Need full tag list for Copter-4.7.* — shallow clone has no tags
  git clone https://github.com/ArduPilot/ardupilot.git
fi

cd "$AP_DIR"
git fetch --tags --force
TAG="$(git tag -l 'Copter-4.7.*' | sort -V | tail -1)"
if [ -z "$TAG" ]; then
  echo "No Copter-4.7.* tag found"
  exit 1
fi
git checkout "$TAG"
git submodule update --init --recursive

if [ -f Tools/environment_install/install-prereqs-ubuntu.sh ]; then
  bash Tools/environment_install/install-prereqs-ubuntu.sh -y || true
fi

./waf configure --board sitl
NPROC="$(nproc 2>/dev/null || echo 4)"
JOBS=$(( NPROC > 2 ? NPROC - 2 : 1 ))
./waf copter -j "$JOBS"

COMMIT="$(git rev-parse HEAD)"
{
  echo "tag=$TAG"
  echo "commit=$COMMIT"
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$LOCK"

echo "Wrote $LOCK; binary: ${AP_DIR}/build/sitl/bin/arducopter"
