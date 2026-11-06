from __future__ import annotations

import json
from pathlib import Path

import pytest

from deadstick.rules.loader import load_rule

RULE_KEYS = ("FS_THR_ENABLE", "FS_OPTIONS", "BATT_FS_LOW_ACT")


def _repo_has_copter_metadata() -> bool:
    root = Path(__file__).resolve().parents[2]
    return any((root / "metadata").glob("Copter-*.json"))


@pytest.mark.skipif(
    not _repo_has_copter_metadata(),
    reason="metadata/Copter-*.json only after build_sitl on RunPod",
)
def test_r01_through_r03_params_in_shipped_metadata(repo_root: Path) -> None:
    meta_files = list((repo_root / "metadata").glob("Copter-*.json"))
    assert meta_files, "expected at least one metadata/Copter-*.json"
    path = meta_files[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    params = data.get("parameters") or {}
    missing = [k for k in RULE_KEYS if k not in params]
    assert not missing, f"Missing in {path.name}: {missing}"

    for rule_name in (
        "r01_rc_loss_disarmed_blocks_arming.yaml",
        "r02_rc_loss_rtl_when_configured.yaml",
        "r03_battery_low_triggers_land.yaml",
    ):
        rf = load_rule(repo_root / "rules" / "copter" / rule_name)
        bad = [p for p in rf.requires_params if p not in params]
        assert not bad, f"{rule_name}: metadata missing requires_params {bad}"
