from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deadstick.verdict import Result


def write_result_json(
    path: Path,
    *,
    rule_id: str,
    results: list[Result],
    provenance: dict[str, Any],
    timeline_path: Path | None = None,
    dataflash_path: Path | None = None,
) -> None:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "results": [
            {
                "verdict": r.verdict.value,
                "reason": r.reason,
                "evidence": r.evidence,
                "provenance": r.provenance,
            }
            for r in results
        ],
        "provenance": provenance,
    }
    if timeline_path is not None:
        payload["timeline_path"] = str(timeline_path)
    if dataflash_path is not None:
        payload["dataflash_path"] = str(dataflash_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
