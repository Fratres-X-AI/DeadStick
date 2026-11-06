from __future__ import annotations

from pathlib import Path


def find_latest_dataflash_bin(workdir: Path) -> Path | None:
    """Return the newest ArduPilot dataflash *.BIN under workdir (prefers logs/)."""
    logs = workdir / "logs"
    roots = [logs, workdir] if logs.is_dir() else [workdir]
    bins: list[Path] = []
    for root in roots:
        bins.extend(root.rglob("*.BIN"))
        bins.extend(root.rglob("*.bin"))
    if not bins:
        return None
    return max(bins, key=lambda p: p.stat().st_mtime)
