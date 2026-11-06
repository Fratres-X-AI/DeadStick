from __future__ import annotations

import logging
from pathlib import Path
from deadstick.timeline.model import Timeline, TimelineEvent

log = logging.getLogger(__name__)


def timeus_to_ms(timeus: float) -> float:
    """Dataflash TimeUS is microseconds; timeline uses milliseconds."""
    return timeus / 1000.0


def bin_to_timeline(path: Path) -> Timeline:
    """
    Convert an ArduPilot dataflash .BIN to Timeline events.

    pymavlink's DFReader is pull-based; we walk messages and map a small set
    of types used by checks (MODE, MSG, EV, CTUN, ERR).
    """
    from pymavlink import mavutil

    reader = mavutil.mavlink_connection(str(path))

    events: list[TimelineEvent] = []
    t0_ms: float | None = None
    types = ("MODE", "MSG", "EV", "ERR", "CTUN")
    while True:
        m = reader.recv_match(type=list(types), blocking=False)
        if m is None:
            break
        name = m.get_type()
        t_ms: float | None = None
        if hasattr(m, "_timestamp") and m._timestamp is not None:
            t_abs_ms = float(m._timestamp) * 1000.0
        elif hasattr(m, "TimeUS") and m.TimeUS is not None:
            t_abs_ms = timeus_to_ms(float(m.TimeUS))
        elif hasattr(m, "time_boot_ms") and m.time_boot_ms is not None:
            t_ms = float(m.time_boot_ms)
            t_abs_ms = None
        else:
            t_abs_ms = None

        if t_ms is None and t_abs_ms is not None:
            if t0_ms is None:
                t0_ms = t_abs_ms
            t_ms = t_abs_ms - t0_ms

        if t_ms is None:
            continue

        if name == "MODE":
            events.append(
                TimelineEvent(
                    t_boot_ms=t_ms,
                    type="mode",
                    payload={"name": getattr(m, "Mode", None) or getattr(m, "mode", "")},
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

    if not events:
        log.warning("No messages parsed from %s — empty or unsupported format", path)
    return Timeline(events)
