from __future__ import annotations

from pathlib import Path

from deadstick.sim.dataflash_log import find_latest_dataflash_bin


def test_find_latest_returns_none_when_only_eeprom_bin(tmp_path: Path) -> None:
    """eeprom.bin in workdir root must not be mistaken for a flight log."""
    (tmp_path / "eeprom.bin").write_bytes(b"\x00" * 8)
    assert find_latest_dataflash_bin(tmp_path) is None
