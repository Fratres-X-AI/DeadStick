from __future__ import annotations

from pathlib import Path


def find_latest_dataflash_bin(workdir: Path) -> Path | None:
    """Return the newest ArduPilot dataflash ``*.BIN`` under ``workdir/logs/`` only.

    Flight logs are under ``logs/`` with an uppercase ``.BIN`` extension. Do not treat
    ``eeprom.bin`` or other non-log binaries in the workdir root as dataflash.
    """
    logs = workdir / "logs"
    if not logs.is_dir():
        return None
    bins = list(logs.glob("*.BIN"))
    if not bins:
        return None
    return max(bins, key=lambda p: p.stat().st_mtime)
