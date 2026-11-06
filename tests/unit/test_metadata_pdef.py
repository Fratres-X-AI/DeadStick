from __future__ import annotations

import json
from pathlib import Path

from deadstick.metadata import load_metadata, param_entry
from deadstick.metadata_norm import normalize_apm_pdef


def test_normalize_apm_pdef_lowercases_values() -> None:
    raw = {
        "json": {"version": 0},
        "ArduCopter": {
            "FS_THR_ENABLE": {
                "Description": "x",
                "Values": {"0": "Disabled", "1": "RTL"},
            }
        },
    }
    out = normalize_apm_pdef(raw)
    ent = param_entry(out, "FS_THR_ENABLE")
    assert ent is not None
    assert ent.get("values") == {"0": "Disabled", "1": "RTL"}


def test_load_metadata_accepts_raw_apm(tmp_path: Path) -> None:
    raw = {"ArduPlane": {"X": {"Values": {"1": "a"}}}}
    p = tmp_path / "apm.pdef.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    loaded = load_metadata(p)
    assert "parameters" in loaded
    assert loaded["source"] == "ardupilot_param_parse"
