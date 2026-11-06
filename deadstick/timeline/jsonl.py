from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deadstick.timeline.model import Timeline, TimelineEvent


def load_jsonl(path: Path) -> Timeline:
    events: list[TimelineEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row: dict[str, Any] = json.loads(line)
        events.append(
            TimelineEvent(
                t_boot_ms=float(row["t_boot_ms"]),
                type=str(row["type"]),
                payload=dict(row.get("payload") or {}),
            )
        )
    return Timeline(events)
