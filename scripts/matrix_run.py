#!/usr/bin/env python3
"""
Parallel matrix: rules x param files x repeats (Linux host).
Requires SITL binaries and metadata; v1 is a skeleton that lists work items.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _effective_cpus() -> int:
    here = Path(__file__).resolve().parent
    py = here / "effective_cpus.py"
    if py.is_file():
        out = subprocess.run(
            [sys.executable, str(py)],
            check=True,
            capture_output=True,
            text=True,
        )
        return max(1, int(out.stdout.strip()))
    return max(1, (os.cpu_count() or 4))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rules-dir", type=Path, default=Path("rules/copter"))
    p.add_argument("--params-glob", default="*.param")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Default: effective cgroup CPUs minus 2",
    )
    args = p.parse_args()

    cpus = _effective_cpus()
    workers = args.workers if args.workers is not None else max(1, cpus - 2)

    rules = sorted(args.rules_dir.glob("*.yaml"))
    print(f"Matrix skeleton: {len(rules)} rules, repeats={args.repeats}, effective_cpus={cpus} workers={workers}")
    print("Full parallel SITL execution is wired in phase 5 after Docker + harness hardening.")


if __name__ == "__main__":
    main()
