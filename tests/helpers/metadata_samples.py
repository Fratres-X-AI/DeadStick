"""Minimal ArduPilot-style parameter metadata shapes for unit tests (inline, not files)."""

from __future__ import annotations

from typing import Any

# Same structure pod-generated metadata will use; not marked `"fake": true`.
MIN_COPTER_METADATA: dict[str, Any] = {
    "parameters": {
        "FS_THR_ENABLE": {
            "values": {
                "0": "Disabled",
                "1": "Enabled RTL on loss",
                "2": "Enabled Land on loss",
            }
        },
        "FS_OPTIONS": {
            "bitmask": {"Continue mission in AUTO on FS": 5},
        },
        "BATT_FS_LOW_ACT": {
            "values": {"0": "None", "1": "Land", "2": "RTL"},
        },
    },
}
