from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from pymavlink import mavutil

from deadstick.timeline.model import Timeline, TimelineEvent


def _mode_name(mav: mavutil.mavlink_connection, hb: Any) -> str:
    if hb.custom_mode is None:
        return "UNKNOWN"
    mapping = mav.mode_mapping() or {}
    inv = {v: k for k, v in mapping.items()}
    return str(inv.get(hb.custom_mode, f"MODE_{hb.custom_mode}"))


def record_mavlink_to_jsonl(
    mav: mavutil.mavlink_connection,
    *,
    out_path: Path,
    duration_s: float,
    poll_hz: float = 50.0,
    append: bool = False,
) -> Timeline:
    """
    Poll inbound MAVLink for a fixed wall duration; map to TimelineEvent rows.
    Vehicle time uses message time_boot_ms when present.
    """
    import time

    events: list[TimelineEvent] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    file_mode = "a" if append else "w"
    f = out_path.open(file_mode, encoding="utf-8")
    t_end = time.monotonic() + duration_s
    last_mode: str | None = None
    try:
        while time.monotonic() < t_end:
            m = mav.recv_match(blocking=False)
            if m is None:
                time.sleep(1.0 / poll_hz)
                continue
            t = getattr(m, "time_boot_ms", None)
            if t is None:
                continue
            t_ms = float(t)
            name = m.get_type()
            if name == "HEARTBEAT":
                current_mode = _mode_name(mav, m)
                if current_mode != last_mode:
                    last_mode = current_mode
                    ev = TimelineEvent(
                        t_boot_ms=t_ms, type="mode", payload={"name": current_mode}
                    )
                    events.append(ev)
                    f.write(
                        json.dumps(
                            {
                                "t_boot_ms": t_ms,
                                "type": "mode",
                                "payload": {"name": current_mode},
                            }
                        )
                        + "\n"
                    )
            elif name == "STATUSTEXT":
                text = getattr(m, "text", b"")
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="replace")
                ev = TimelineEvent(t_boot_ms=t_ms, type="statustext", payload={"text": text})
                events.append(ev)
                f.write(
                    json.dumps({"t_boot_ms": t_ms, "type": "statustext", "payload": {"text": text}})
                    + "\n"
                )
            elif name == "GLOBAL_POSITION_INT":
                rel_m = getattr(m, "relative_alt", None)
                if rel_m is not None:
                    ev = TimelineEvent(
                        t_boot_ms=t_ms,
                        type="position",
                        payload={"rel_alt_m": float(rel_m) / 1000.0},
                    )
                    events.append(ev)
                    f.write(
                        json.dumps(
                            {
                                "t_boot_ms": t_ms,
                                "type": "position",
                                "payload": {"rel_alt_m": float(rel_m) / 1000.0},
                            }
                        )
                        + "\n"
                    )
    finally:
        f.close()
    return Timeline(events)


def poll_mavlink_to_timeline(
    mav: mavutil.mavlink_connection,
    *,
    out_path: Path,
    duration_s: float,
    poll_hz: float = 50.0,
    append: bool = False,
) -> Timeline:
    """Alias for :func:`record_mavlink_to_jsonl` (scenario steps use this name)."""
    return record_mavlink_to_jsonl(
        mav,
        out_path=out_path,
        duration_s=duration_s,
        poll_hz=poll_hz,
        append=append,
    )


def append_events(path: Path, events: Iterable[TimelineEvent]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for e in events:
            f.write(
                json.dumps(
                    {"t_boot_ms": e.t_boot_ms, "type": e.type, "payload": e.payload},
                    ensure_ascii=False,
                )
                + "\n"
            )
