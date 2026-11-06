from __future__ import annotations

import logging
from pathlib import Path

from deadstick.timeline.model import Timeline, TimelineEvent

log = logging.getLogger(__name__)


def timeus_to_ms(timeus: float) -> float:
    """Dataflash TimeUS is microseconds; timeline uses milliseconds since boot."""
    return timeus / 1000.0


def acm_mode_num_to_name(num: float | int) -> tuple[str, int]:
    """Map ArduCopter custom_mode number to mode name using pymavlink's ACM table."""
    from pymavlink import mavutil

    n = int(num)
    mm = mavutil.mode_mapping_acm
    if callable(mm):
        mm = mm()
    # pymavlink exposes number → name (e.g. 6 → "RTL")
    name = str(mm.get(n, f"UNKNOWN_{n}"))
    return name, n


def bin_to_timeline(path: Path, *, params: dict[str, float] | None = None) -> Timeline:
    """
    Convert an ArduPilot dataflash .BIN to Timeline events.

    Uses TimeUS / 1000 as t_boot_ms (time since boot). Does not use pymavlink's
    wall-clock _timestamp — it is not comparable to live-link time_boot_ms.

    Emits fault_injected from PARM rows: SIM_RC_FAIL != 0 (rc_loss), and
    SIM_BATT_VOLTAGE below BATT_LOW_VOLT only when that threshold exists in params.
    """
    from pymavlink import mavutil

    reader = mavutil.mavlink_connection(str(path))

    events: list[TimelineEvent] = []
    batt_low_v: float | None = None
    if params and "BATT_LOW_VOLT" in params:
        batt_low_v = float(params["BATT_LOW_VOLT"])

    types = ("MODE", "MSG", "EV", "ERR", "CTUN", "PARM")
    while True:
        m = reader.recv_match(type=list(types), blocking=False)
        if m is None:
            break
        name = m.get_type()

        if not hasattr(m, "TimeUS") or m.TimeUS is None:
            continue
        t_ms = timeus_to_ms(float(m.TimeUS))

        if name == "MODE":
            raw_num = getattr(m, "ModeNum", None)
            if raw_num is None:
                raw_num = getattr(m, "Mode", None)
            if raw_num is None:
                continue
            mode_name, num = acm_mode_num_to_name(raw_num)
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="mode",
                    payload={"name": mode_name, "num": num},
                )
            )
        elif name == "MSG":
            text = getattr(m, "Message", "") or ""
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="statustext",
                    payload={"text": str(text)},
                )
            )
        elif name == "EV":
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="event",
                    payload={"id": getattr(m, "Id", None), "raw": m.to_dict()},
                )
            )
        elif name == "ERR":
            sub = getattr(m, "Subsys", None)
            code = getattr(m, "ECode", None)
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="err",
                    payload={"subsys": sub, "ecode": code},
                )
            )
        elif name == "CTUN":
            alt = getattr(m, "Alt", None)
            dalt = getattr(m, "DAlt", None)
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="position",
                    payload={
                        "rel_alt_m": float(alt) if alt is not None else None,
                        "dalt_m": float(dalt) if dalt is not None else None,
                    },
                )
            )
        elif name == "PARM":
            pname = str(getattr(m, "Name", "") or "").strip()
            try:
                val = float(getattr(m, "Value", 0.0))
            except (TypeError, ValueError):
                val = 0.0
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="parm",
                    payload={"name": pname, "value": val},
                )
            )
            if pname == "SIM_RC_FAIL" and val != 0.0:
                events.append(
                    TimelineEvent(
                        t_boot_ms=t_ms,
                        type="fault_injected",
                        payload={"kind": "rc_loss", "source": "PARM_SIM_RC_FAIL"},
                    )
                )
            elif pname == "SIM_BATT_VOLTAGE" and batt_low_v is not None and val > 0.0 and val < batt_low_v:
                events.append(
                    TimelineEvent(
                        t_boot_ms=t_ms,
                        type="fault_injected",
                        payload={"kind": "battery_low", "source": "PARM_SIM_BATT_VOLTAGE"},
                    )
                )

    if not events:
        log.warning("No messages parsed from %s — empty or unsupported format", path)
    return Timeline(events)
