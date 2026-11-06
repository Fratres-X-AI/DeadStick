from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_metadata(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("fake") is True:
        return raw
    if "parameters" in raw:
        return raw
    from deadstick.metadata_norm import normalize_apm_pdef

    return normalize_apm_pdef(raw)


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


def bitmask_bits_set(value: int, bitmask: dict[str, Any]) -> set[int]:
    """
    Return indices of bits set in value.

    Supports:
    - ArduPilot apm.pdef / normalized JSON: key is bit index (string), value is label.
    - Inline test fixtures: key is label, value is bit index (int).
    """
    out: set[int] = set()
    if not bitmask:
        return out
    sample_k = next(iter(bitmask.keys()))
    if str(sample_k).isdigit():
        for k in bitmask.keys():
            bi = int(k)
            if (value >> bi) & 1:
                out.add(bi)
        return out
    for _name, bit in bitmask.items():
        bi = int(bit)
        if (value >> bi) & 1:
            out.add(bi)
    return out
