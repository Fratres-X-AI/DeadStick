from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pymavlink import mavutil

from deadstick.sim import scenario_engine


class _GP:
    def __init__(self) -> None:
        self.lat = int(-35.363261 * 1.0e7)
        self.lon = int(149.165230 * 1.0e7)
        self.relative_alt = int(20_000)


def test_move_north_uses_global_relative_alt_int_frame(tmp_path: Path) -> None:
    mav = MagicMock()
    gp = _GP()

    def recv_match(type=None, blocking=False, timeout=None):
        if type == "GLOBAL_POSITION_INT":
            return gp
        return None

    mav.recv_match.side_effect = recv_match
    mav.target_system = 1
    mav.target_component = 1

    fi = MagicMock()
    times = iter([0.0, 0.0, 5.0, 10.0, 70.0])

    def mono():
        try:
            return next(times)
        except StopIteration:
            return 200.0

    with patch("deadstick.sim.scenario_engine._haversine_m", return_value=95.0):
        with patch.object(scenario_engine, "poll_mavlink_to_timeline", lambda *a, **kw: None):
            with patch("deadstick.sim.scenario_engine.time.monotonic", side_effect=mono):
                with patch("deadstick.sim.scenario_engine.time.sleep"):
                    scenario_engine._exec_step(
                        "move_north",
                        {"m": 100.0},
                        mav=mav,
                        fi=fi,
                        timeline_path=tmp_path / "tl.jsonl",
                        t_now=lambda: 0.0,
                        observe_after_inject_s=1.0,
                    )

    mav.mav.command_int_send.assert_called_once()
    args = mav.mav.command_int_send.call_args[0]
    assert args[2] == mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT


def test_move_north_polls_until_distance_and_alt(tmp_path: Path) -> None:
    mav = MagicMock()
    gp0 = _GP()

    def recv_match(type=None, blocking=False, timeout=None):
        if type == "GLOBAL_POSITION_INT":
            return gp0
        return None

    mav.recv_match.side_effect = recv_match
    mav.target_system = 1
    mav.target_component = 1

    fi = MagicMock()
    times = iter([0.0, 0.0, 5.0, 10.0, 70.0])

    def mono():
        try:
            return next(times)
        except StopIteration:
            return 200.0

    with patch("deadstick.sim.scenario_engine._haversine_m", return_value=95.0):
        with patch.object(scenario_engine, "poll_mavlink_to_timeline", lambda *a, **kw: None):
            with patch("deadstick.sim.scenario_engine.time.monotonic", side_effect=mono):
                with patch("deadstick.sim.scenario_engine.time.sleep"):
                    scenario_engine._exec_step(
                        "move_north",
                        {"m": 100.0},
                        mav=mav,
                        fi=fi,
                        timeline_path=tmp_path / "tl.jsonl",
                        t_now=lambda: 0.0,
                        observe_after_inject_s=1.0,
                    )

    assert mav.mav.command_int_send.called
