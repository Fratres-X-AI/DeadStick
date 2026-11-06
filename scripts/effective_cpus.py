#!/usr/bin/env python3
"""Print effective CPU count for cgroup quota (Linux host), else os.cpu_count()."""
from __future__ import annotations

import math
import os
from pathlib import Path


def _ceiling_div(a: int, b: int) -> int:
    if b <= 0:
        return 1
    return max(1, (a + b - 1) // b)


def effective_cpus() -> int:
    # cgroup v2
    cpu_max = Path("/sys/fs/cgroup/cpu.max")
    if cpu_max.is_file():
        text = cpu_max.read_text().strip().split()
        if len(text) >= 2:
            quota, period = text[0], text[1]
            if quota == "max":
                return os.cpu_count() or 1
            try:
                q, p = int(quota), int(period)
                return _ceiling_div(q, p) if p > 0 else os.cpu_count() or 1
            except ValueError:
                pass

    # cgroup v1
    qpath = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    ppath = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if qpath.is_file() and ppath.is_file():
        try:
            q = int(qpath.read_text().strip())
            p = int(ppath.read_text().strip())
            if q > 0 and p > 0:
                return _ceiling_div(q, p)
        except ValueError:
            pass

    return os.cpu_count() or 1


if __name__ == "__main__":
    print(effective_cpus())
