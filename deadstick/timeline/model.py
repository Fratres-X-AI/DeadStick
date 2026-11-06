from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class TimelineEvent:
    """One row in the vehicle timeline. Clock is always milliseconds since boot."""

    t_boot_ms: float
    type: str
    payload: dict[str, Any]


class Timeline:
    """Ordered vehicle events. Built from JSONL, MAVLink recorder, or dataflash."""

    def __init__(self, events: list[TimelineEvent]) -> None:
        self._events = sorted(events, key=lambda e: e.t_boot_ms)

    @property
    def events(self) -> list[TimelineEvent]:
        return list(self._events)

    def first(
        self,
        etype: str,
        *,
        after_ms: Optional[float] = None,
        where: Optional[Callable[[TimelineEvent], bool]] = None,
    ) -> Optional[TimelineEvent]:
        for e in self._events:
            if after_ms is not None and e.t_boot_ms < after_ms:
                continue
            if e.type != etype:
                continue
            if where is not None and not where(e):
                continue
            return e
        return None

    def between(self, t0_ms: float, t1_ms: float) -> list[TimelineEvent]:
        return [e for e in self._events if t0_ms <= e.t_boot_ms <= t1_ms]

    def mode_at(self, t_ms: float) -> Optional[str]:
        last: Optional[str] = None
        for e in self._events:
            if e.type != "mode":
                continue
            if e.t_boot_ms > t_ms:
                break
            last = str(e.payload.get("name", ""))
        return last

    def max_rel_alt_between(self, t0_ms: float, t1_ms: float) -> Optional[float]:
        best: Optional[float] = None
        for e in self.between(t0_ms, t1_ms):
            if e.type != "position":
                continue
            alt = e.payload.get("rel_alt_m")
            if alt is None:
                continue
            v = float(alt)
            best = v if best is None else max(best, v)
        return best
