from __future__ import annotations

from pathlib import Path

from deadstick.evaluate.runner import evaluate_rule
from deadstick.param_file import load_param_file
from deadstick.rules.loader import load_rule
from deadstick.timeline.jsonl import load_jsonl
from deadstick.verdict import Verdict

from tests.helpers.metadata_samples import MIN_COPTER_METADATA

FIX = Path("tests/fixtures/params/bad")


def _base_radio_timeline() -> list[str]:
    return [
        '{"t_boot_ms": 2000, "type": "fault_injected", "payload": {"kind": "rc_loss_in_air"}}',
        '{"t_boot_ms": 2500, "type": "statustext", "payload": {"text": "Radio failsafe triggered"}}',
        '{"t_boot_ms": 1000, "type": "mode", "payload": {"name": "STABILIZE"}}',
        '{"t_boot_ms": 2100, "type": "mode", "payload": {"name": "RTL"}}',
    ]


def test_fs_thr_off_r02_requirement_fail(repo_root: Path, tmp_path: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(repo_root / FIX / "fs_thr_off.param")
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(_base_radio_timeline()) + "\n", encoding="utf-8")
    tl = load_jsonl(p)
    r = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert r[0].verdict is Verdict.FAIL


def test_fs_thr_off_r01_conformance_cannot_judge(repo_root: Path, tmp_path: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r01_rc_loss_disarmed_blocks_arming.yaml")
    params = load_param_file(repo_root / FIX / "fs_thr_off.param")
    p = tmp_path / "t.jsonl"
    p.write_text(
        "\n".join(
            [
                '{"t_boot_ms": 1000, "type": "fault_injected", "payload": {"kind": "rc"}}',
                '{"t_boot_ms": 1010, "type": "statustext", "payload": {"text": "Radio failsafe triggered"}}',
                '{"t_boot_ms": 920, "type": "statustext", "payload": {"text": "PreArm: ok"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tl = load_jsonl(p)
    r = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert r[0].verdict is Verdict.CANNOT_JUDGE


def test_batt_none_r03_requirement_fail(repo_root: Path, tmp_path: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r03_battery_low_triggers_land.yaml")
    params = load_param_file(repo_root / FIX / "batt_none.param")
    p = tmp_path / "t.jsonl"
    p.write_text(
        "\n".join(
            [
                '{"t_boot_ms": 3000, "type": "fault_injected", "payload": {"kind": "battery_low"}}',
                '{"t_boot_ms": 3010, "type": "statustext", "payload": {"text": "Battery failsafe triggered"}}',
                '{"t_boot_ms": 3200, "type": "mode", "payload": {"name": "LAND"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tl = load_jsonl(p)
    r = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert r[0].verdict is Verdict.FAIL
