from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deadstick.repo import REPO_ROOT
from deadstick.verdict import Result


def _repo_relative_str(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


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
        payload["timeline_path"] = _repo_relative_str(timeline_path)
    if dataflash_path is not None:
        payload["dataflash_path"] = _repo_relative_str(dataflash_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
