from __future__ import annotations

import re
from pathlib import Path


def load_param_file(path: Path) -> dict[str, float]:
    """
    Minimal ArduPilot/Mission Planner .param parser.
    Lines: NAME,value  or  NAME<TAB>value
    """
    out: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([^,\s]+)\s*[, \t]+\s*([^\s#]+)", line)
        if not m:
            continue
        name, val = m.group(1), m.group(2)
        try:
            num = float(val)
        except ValueError:
            continue
        out[name] = num
    return out
