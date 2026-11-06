from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_metadata(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("fake") is True:
        return raw
    return raw


def assert_not_fake_metadata(path: Path, data: dict[str, Any]) -> None:
    name = path.name
    if name.upper().startswith("FAKE_") or data.get("fake") is True:
        raise ValueError(
            "Refusing real verdict: metadata is marked fake (filename FAKE_ or "
            'JSON "fake": true). Use generated metadata from the pod.'
        )


def param_entry(metadata: dict[str, Any], name: str) -> dict[str, Any] | None:
    """
    FAKE file shape: {"parameters": {"FS_THR_ENABLE": {"values": {"0":"Disabled",...}}}}
    Real generated file may differ; extend when pod metadata lands.
    """
    params = metadata.get("parameters")
    if not isinstance(params, dict):
        return None
    ent = params.get(name)
    return ent if isinstance(ent, dict) else None


def bitmask_bits_set(value: int, bitmask: dict[str, int]) -> set[int]:
    """Bitmask map: bit name -> bit index (0-based)."""
    out: set[int] = set()
    for _k, bit in bitmask.items():
        if (value >> int(bit)) & 1:
            out.add(int(bit))
    return out
