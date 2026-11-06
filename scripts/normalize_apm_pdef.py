#!/usr/bin/env python3
"""
Flatten ArduPilot apm.pdef.json (from param_parse.py --format=json) into DeadStick shape:
  {"parameters": { "NAME": { "values": {...}, "bitmask": {...} } } }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as script without package on PYTHONPATH
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from deadstick.metadata_norm import normalize_apm_pdef  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path, help="apm.pdef.json from ardupilot tree")
    p.add_argument("output", type=Path, help="metadata/Copter-X.Y.Z.json")
    args = p.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    out = normalize_apm_pdef(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
