#!/usr/bin/env bash
# Regenerate normalized Copter metadata and ardupilot.lock when ardupilot/ is already
# checked out (assumes ./waf copter was run). Compiles ArduPilot SITL; slow, many cores.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AP_DIR="${ROOT}/ardupilot"
META_DIR="${ROOT}/metadata"
LOCK="${ROOT}/ardupilot.lock"

cd "$AP_DIR"
git fetch --tags --force
TAG="$(git tag -l 'Copter-4.7.*' | grep -Ev 'beta|rc' | sort -V | tail -1)"
if [ -z "$TAG" ]; then
  echo "No Copter-4.7.* stable tag"
  exit 1
fi
echo "Using tag $TAG"
git checkout "$TAG"
git submodule update --init --recursive

NPROC="$(nproc 2>/dev/null || echo 4)"
JOBS=$(( NPROC > 2 ? NPROC - 2 : 1 ))
./waf configure --board sitl
./waf copter -j "$JOBS"

mkdir -p "$META_DIR"
cd "$AP_DIR"
if python3 Tools/autotest/param_metadata/param_parse.py --help 2>&1 | grep -q no-legacy-params; then
  python3 Tools/autotest/param_metadata/param_parse.py --vehicle=Copter --format=json --no-legacy-params
else
  python3 Tools/autotest/param_metadata/param_parse.py --vehicle=Copter --format=json
fi
cp -f "${AP_DIR}/apm.pdef.json" "${META_DIR}/apm.pdef.raw.json"
OUT_META="${META_DIR}/${TAG}.json"
python3 "${ROOT}/scripts/normalize_apm_pdef.py" "${META_DIR}/apm.pdef.raw.json" "$OUT_META"
META_HASH="$(sha256sum "$OUT_META" | awk '{print $1}')"
COMMIT="$(git -C "$AP_DIR" rev-parse HEAD)"
{
  echo "tag=$TAG"
  echo "commit=$COMMIT"
  echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "metadata_json=$OUT_META"
  echo "metadata_sha256=$META_HASH"
} > "$LOCK"
echo "Wrote $LOCK"
cat "$LOCK"
ls -la "$OUT_META" "${AP_DIR}/build/sitl/bin/arducopter"
