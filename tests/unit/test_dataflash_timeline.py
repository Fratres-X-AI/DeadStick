from __future__ import annotations

from unittest.mock import MagicMock

from deadstick.timeline.dataflash import acm_mode_num_to_name, timeus_to_ms


def test_timeus_maps_to_boot_ms() -> None:
    assert timeus_to_ms(12_345_000) == 12345.0


def test_mode_num_6_is_rtl() -> None:
    name, num = acm_mode_num_to_name(6)
    assert num == 6
    assert name == "RTL"
