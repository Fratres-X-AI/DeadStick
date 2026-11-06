from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pymavlink import mavutil

from deadstick.param_file import load_param_file
from deadstick.timeline.model import TimelineEvent


def connect(tcp: str = "tcp:127.0.0.1:5760") -> mavutil.mavlink_connection:
    """
    Connect to SITL SERIAL0. **Must** use the ``tcp:`` prefix: bare ``host:port`` is
    opened as **UDP** in pymavlink, while ArduPilot SITL listens on TCP.
    """
    return mavutil.mavlink_connection(tcp, autoreconnect=True)


def connect_with_retry(url: str, *, timeout_s: float = 90.0) -> mavutil.mavlink_connection:
    """Connect with pymavlink and wait for HEARTBEAT; retry until *timeout_s*.

    Avoid raw TCP probes: opening and closing TCP to SERIAL0 breaks the real MAVLink
    session on ArduPilot SITL. The first successful connection attempt is what keeps
    the link stable for the vehicle.
    """
    deadline = time.monotonic() + float(timeout_s)
    while time.monotonic() < deadline:
        conn: mavutil.mavlink_connection | None = None
        try:
            conn = mavutil.mavlink_connection(url, autoreconnect=True)
            hb_deadline = time.monotonic() + 5.0
            while time.monotonic() < hb_deadline:
                m = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
                if m is not None:
                    return conn
        except Exception:
            pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        time.sleep(1.0)
    raise TimeoutError(f"No HEARTBEAT from {url!r} within {timeout_s}s")


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


def vehicle_time_boot_ms(mav: mavutil.mavlink_connection) -> float:
    """Best-effort `time_boot_ms` from the most recently received MAVLink message."""
    # Drain a few non-blocking reads to refresh last message time
    for _ in range(32):
        m = mav.recv_match(blocking=False)
        if m is None:
            break
        t = getattr(m, "time_boot_ms", None)
        if t is not None:
            return float(t)
    # Fallback: block briefly for any traffic
    m = mav.recv_match(blocking=True, timeout=2)
    if m is not None and getattr(m, "time_boot_ms", None) is not None:
        return float(m.time_boot_ms)
    return 0.0


def set_mode_apm(mav: mavutil.mavlink_connection, mode_name: str) -> bool:
    """Set ArduCopter mode by name (e.g. GUIDED, LAND)."""
    mapping = mav.mode_mapping()
    if not mapping:
        return False
    want = mode_name.strip().upper()
    for name in mapping:
        if name.upper() == want:
            return bool(mav.set_mode(name))
    return False


def send_arm_command(
    mav: mavutil.mavlink_connection,
    arm: bool,
    *,
    timeout_s: float = 10.0,
) -> tuple[bool, int | None]:
    """
    Arm or disarm. Returns (accepted, result_code from COMMAND_ACK or None).
    """
    mav.mav.command_long_send(
        mav.target_system,
        mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1.0 if arm else 0.0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        ack = mav.recv_match(type="COMMAND_ACK", blocking=False)
        if ack is None:
            time.sleep(0.05)
            continue
        if ack.command != mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            continue
        return ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED, int(ack.result)
    return False, None


def drain_ack_results(
    mav: mavutil.mavlink_connection,
    command: int,
    *,
    timeout_s: float = 2.0,
) -> list[int]:
    """Collect COMMAND_ACK result codes for a MAV_CMD within a short window."""
    deadline = time.monotonic() + timeout_s
    out: list[int] = []
    while time.monotonic() < deadline:
        ack = mav.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.1)
        if ack is None:
            continue
        if int(ack.command) != int(command):
            continue
        out.append(int(ack.result))
    return out


def tcp_url_for_sitl_instance(
    host: str = "127.0.0.1",
    tcp_base_port: int = 5760,
    instance: int = 0,
) -> str:
    """SERIAL0 for SITL instance *n* is tcp on port 5760 + 10*n."""
    port = int(tcp_base_port) + int(instance) * 10
    return f"tcp:{host}:{port}"


def preflight_reboot(mav: mavutil.mavlink_connection) -> None:
    """Request an autopilot reboot (ArduPilot `MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN`, param1=1)."""
    mav.mav.command_long_send(
        mav.target_system,
        mav.target_component,
        mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
        0,
        1.0,  # reboot autopilot
        0,
        0,
        0,
        0,
        0,
        0,
    )


def reboot_and_reconnect(url: str, *, settle_s: float = 5.0) -> mavutil.mavlink_connection:
    """Send reboot on *url*, then reconnect with MAVLink retry (no raw TCP probe)."""
    mav = connect_with_retry(url)
    preflight_reboot(mav)
    try:
        mav.close()
    except Exception:
        pass
    time.sleep(settle_s)
    return connect_with_retry(url, timeout_s=90.0)
