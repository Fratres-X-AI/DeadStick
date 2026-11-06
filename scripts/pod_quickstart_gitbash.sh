#!/usr/bin/env bash
# Run from Git Bash on Windows (or any bash) after: export RUNPOD_SSH='user@host -p PORT'
# HEAVY: builds SITL, runs pulse loop, optional sitl-run — use only on the pod you pay for.
set -euo pipefail

: "${RUNPOD_SSH:?Set RUNPOD_SSH, e.g. export RUNPOD_SSH='root@1.2.3.4 -p 12345'}"

REMOTE_DIR="${REMOTE_DIR:-/root/DeadStick}"

ssh $RUNPOD_SSH bash -s <<EOF
set -euo pipefail
cd "$REMOTE_DIR"
git fetch origin && git pull --ff-only origin main || git pull --ff-only

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -U pip
pip install -q -e ".[dev]"

bash scripts/build_sitl.sh

# Optional: keep CPU busy during long steps (20 x 120s); run in background — kill with pod when done
nohup bash scripts/pod_pulse.sh 20 120 >> /tmp/deadstick_pulse.log 2>&1 &

pytest tests/unit -q

# Paths after build — minimal params for r01 (FS on); adjust for other rules
AP="\$PWD/ardupilot/build/sitl/bin/arducopter"
META="\$(ls -1 metadata/Copter-*.json 2>/dev/null | head -1)"
PARAM_TMP="/tmp/deadstick_r01.param"
cat > "\$PARAM_TMP" <<'PARM'
FS_THR_ENABLE,1
FS_OPTIONS,0
LOG_DISARMED,1
PARM
if [[ -x "\$AP" && -n "\$META" ]]; then
  deadstick sitl-run -r rules/copter/r01_rc_loss_disarmed_blocks_arming.yaml \\
    -p "\$PARAM_TMP" \\
    -m "\$META" \\
    --arducopter "\$AP" \\
    --results-dir results || true
else
  echo "Skip sitl-run: missing arducopter or metadata (run build_sitl first)."
fi
EOF
