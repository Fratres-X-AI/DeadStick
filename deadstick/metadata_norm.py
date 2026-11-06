"""Normalize ArduPilot apm.pdef.json into DeadStick metadata shape."""

from __future__ import annotations

from typing import Any


def normalize_apm_pdef(raw: dict[str, Any]) -> dict[str, Any]:
    """Merge param groups and lowercase Values/Bitmask keys for expectations."""
    flat: dict[str, Any] = {}
    for group_name, group_val in raw.items():
        if group_name == "json":
            continue
        if not isinstance(group_val, dict):
            continue
        flat.update(group_val)

    parameters: dict[str, Any] = {}
    for name, ent in flat.items():
        if not isinstance(ent, dict):
            continue
        e = dict(ent)
        if "Values" in e:
            e["values"] = e.pop("Values")
        if "Bitmask" in e:
            e["bitmask"] = e.pop("Bitmask")
        if "Range" in e:
            e["range"] = e.pop("Range")
        parameters[name] = e

    return {"parameters": parameters, "source": "ardupilot_param_parse"}
