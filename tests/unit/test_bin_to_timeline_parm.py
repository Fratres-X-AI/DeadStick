from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from deadstick.timeline.dataflash import bin_to_timeline


def _make_parm_msg(name: str, value: float, time_us: float = 1_000_000.0) -> MagicMock:
    m = MagicMock()
    m.get_type.return_value = "PARM"
    m.TimeUS = time_us
    m.Name = name
    m.Value = value
    return m


def test_no_battery_fault_without_batt_low_volt() -> None:
    seq = [_make_parm_msg("SIM_BATT_VOLTAGE", 9.0)]
    fake_mav = MagicMock()
    fake_mav.recv_match.side_effect = seq + [None]

    with patch("pymavlink.mavutil.mavlink_connection", return_value=fake_mav):
        tl = bin_to_timeline(Path("dummy.BIN"), params={})

    kinds = [e.payload.get("kind") for e in tl.events if e.type == "fault_injected"]
    assert kinds == []


def test_battery_fault_when_threshold_present() -> None:
    seq = [_make_parm_msg("SIM_BATT_VOLTAGE", 9.0)]
    fake_mav = MagicMock()
    fake_mav.recv_match.side_effect = seq + [None]

    with patch("pymavlink.mavutil.mavlink_connection", return_value=fake_mav):
        tl = bin_to_timeline(Path("dummy.BIN"), params={"BATT_LOW_VOLT": 10.5})

    kinds = [e.payload.get("kind") for e in tl.events if e.type == "fault_injected"]
    assert kinds == ["battery_low"]


def test_rc_fail_parm_emits_fault_at_timeus() -> None:
    time_us = 12_345_000.0
    seq = [_make_parm_msg("SIM_RC_FAIL", 1.0, time_us=time_us)]
    fake_mav = MagicMock()
    fake_mav.recv_match.side_effect = seq + [None]

    with patch("pymavlink.mavutil.mavlink_connection", return_value=fake_mav):
        tl = bin_to_timeline(Path("dummy.BIN"), params={})

    f = [e for e in tl.events if e.type == "fault_injected"]
    assert len(f) == 1
    assert f[0].payload.get("kind") == "rc_loss"
    assert f[0].t_boot_ms == time_us / 1000.0
