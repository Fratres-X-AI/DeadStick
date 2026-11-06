from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pymavlink import mavutil

from deadstick.param_file import load_param_file
from deadstick.timeline.model import TimelineEvent


def connect(tcp: str = "127.0.0.1:5760") -> mavutil.mavlink_connection:
    return mavutil.mavlink_connection(tcp, autoreconnect=True)


def wait_heartbeat(mav: mavutil.mavlink_connection, timeout_s: float = 30.0) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        m = mav.recv_match(type="HEARTBEAT", blocking=False)
        if m:
            return
        time.sleep(0.05)
    raise TimeoutError("No HEARTBEAT")


def fetch_all_params(mav: mavutil.mavlink_connection) -> dict[str, float]:
    mav.param_fetch_all()
    params: dict[str, float] = {}
    t0 = time.monotonic()
    while time.monotonic() - t0 < 30.0:
        m = mav.recv_match(type="PARAM_VALUE", blocking=False)
        if m is None:
            time.sleep(0.01)
            continue
        params[str(m.param_id).strip("\x00")] = float(m.param_value)
        if m.param_count and len(params) >= m.param_count:
            break
    return params


def set_param(
    mav: mavutil.mavlink_connection,
    name: str,
    value: float,
    *,
    timeout_s: float = 5.0,
) -> bool:
    mav.mav.param_set_send(
        mav.target_system,
        mav.target_component,
        name.encode("ascii"),
        value,
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    )
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        m = mav.recv_match(type="PARAM_VALUE", blocking=False)
        if m is None:
            time.sleep(0.02)
            continue
        if str(m.param_id).strip("\x00") == name and abs(float(m.param_value) - value) < 1e-5:
            return True
    return False


def apply_param_file(
    mav: mavutil.mavlink_connection,
    param_path: Path,
) -> tuple[dict[str, float], list[str], list[str]]:
    """Apply each line from .param; return (read_back, not_found, rejected)."""
    desired = load_param_file(param_path)
    not_found: list[str] = []
    rejected: list[str] = []
    known = fetch_all_params(mav)
    for k, v in desired.items():
        if k not in known:
            not_found.append(k)
            continue
        if not set_param(mav, k, v):
            rejected.append(k)
    final = fetch_all_params(mav)
    return final, not_found, rejected


def vehicle_boot_ms(mav: mavutil.mavlink_connection) -> int:
    """Best-effort boot time from last message."""
    m = mav.recv_match(blocking=False)
    if m is not None and getattr(m, "time_boot_ms", None) is not None:
        return int(m.time_boot_ms)
    return 0


def append_param_timeline_events(
    params: dict[str, float],
    t_ms: float,
) -> list[TimelineEvent]:
    return [
        TimelineEvent(t_boot_ms=t_ms, type="param", payload={"name": k, "value": v})
        for k, v in sorted(params.items())
    ]
