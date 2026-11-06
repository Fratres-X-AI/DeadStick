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
TAG="$(git tag -l 'Copter-4.7.*' | grep -Ev 'beta|rc' | sort -V | tail -1)"
if [ -z "$TAG" ]; then
  echo "No Copter-4.7.* tag found"
  exit 1
fi
git checkout "$TAG"
git submodule update --init --recursive

if [ -f Tools/environment_install/install-prereqs-ubuntu.sh ]; then
  bash Tools/environment_install/install-prereqs-ubuntu.sh -y
fi

./waf configure --board sitl
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NPROC="$("$SCRIPT_DIR/cgroup_effective_cpus.sh" 2>/dev/null || nproc 2>/dev/null || echo 4)"
JOBS=$(( NPROC > 2 ? NPROC - 2 : 1 ))
echo "effective_cpus=$NPROC waf_jobs=$JOBS (cgroup-first)" | tee -a "${ROOT}/sitl_build.log" >> /tmp/deadstick_sitl_build.log
./waf copter -j "$JOBS"

COMMIT="$(git rev-parse HEAD)"

META_DIR="${ROOT}/metadata"
mkdir -p "$META_DIR"
(
  cd "$AP_DIR"
  if python3 Tools/autotest/param_metadata/param_parse.py --help 2>&1 | grep -q no-legacy-params; then
    python3 Tools/autotest/param_metadata/param_parse.py --vehicle=Copter --format=json --no-legacy-params
  else
    python3 Tools/autotest/param_metadata/param_parse.py --vehicle=Copter --format=json
  fi
)
cp -f "${AP_DIR}/apm.pdef.json" "${META_DIR}/apm.pdef.raw.json"
OUT_META="${META_DIR}/Copter-${TAG}.json"
python3 "${ROOT}/scripts/normalize_apm_pdef.py" "${META_DIR}/apm.pdef.raw.json" "$OUT_META"
META_HASH="$(sha256sum "$OUT_META" | awk '{print $1}')"

{
  echo "tag=$TAG"
  echo "commit=$COMMIT"
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "metadata_json=$OUT_META"
  echo "metadata_sha256=$META_HASH"
} > "$LOCK"

echo "Wrote $LOCK; binary: ${AP_DIR}/build/sitl/bin/arducopter"
echo "Metadata: $OUT_META"
