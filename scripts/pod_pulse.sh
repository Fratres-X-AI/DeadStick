#!/usr/bin/env bash
# Run on the pod: heartbeat + light CPU so the box isn't idle (20 x 120s = 40 min).
set -euo pipefail
N="${1:-20}"
INTERVAL="${2:-120}"
for i in $(seq 1 "$N"); do
  echo "=== pulse $i/$N $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  uptime
  if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader || true; fi
  # ~5s of CPU-bound work (portable: Python hash loop)
  python3 - <<'PY' &
import hashlib
h = hashlib.sha256()
for _ in range(8_000_000):
    h.update(b"x")
print(h.hexdigest()[:16])
PY
  wait
  if [ "$i" -lt "$N" ]; then sleep "$INTERVAL"; fi
done
echo "pulse done"
