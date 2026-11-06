#!/usr/bin/env python3
"""
[HEAVY] Parallel matrix: rules x param files x repeats (RunPod).
Requires SITL binaries and metadata; v1 is a skeleton that lists work items.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rules-dir", type=Path, default=Path("rules/copter"))
    p.add_argument("--params-glob", default="*.param")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = p.parse_args()

    rules = sorted(args.rules_dir.glob("*.yaml"))
    print(f"Matrix skeleton: {len(rules)} rules, repeats={args.repeats}, workers={args.workers}")
    print("Full parallel SITL execution is wired in phase 5 after Docker + harness hardening.")


if __name__ == "__main__":
    main()
