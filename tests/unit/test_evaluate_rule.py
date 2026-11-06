from __future__ import annotations

import json
from pathlib import Path

from deadstick.evaluate.runner import evaluate_rule
from deadstick.param_file import load_param_file
from deadstick.rules.loader import load_rule
from deadstick.timeline.jsonl import load_jsonl
from deadstick.verdict import Verdict

from tests.helpers.metadata_samples import MIN_COPTER_METADATA


def _write_param(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _write_jsonl(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fault(t: float, kind: str = "rc_loss") -> str:
    return json.dumps(
        {"t_boot_ms": t, "type": "fault_injected", "payload": {"kind": kind}}
    )


def _radio_confirm(t: float) -> str:
    return json.dumps(
        {
            "t_boot_ms": t,
            "type": "statustext",
            "payload": {"text": "Radio failsafe triggered"},
        }
    )


def test_r02_pass_rc_loss_rtl(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,1\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(2000.0, "rc_loss_in_air"),
                _radio_confirm(2500.0),
                '{"t_boot_ms": 1000, "type": "mode", "payload": {"name": "STABILIZE"}}',
                '{"t_boot_ms": 2100, "type": "mode", "payload": {"name": "RTL"}}',
                '{"t_boot_ms": 2200, "type": "position", "payload": {"rel_alt_m": 10.0}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert len(results) == 1
    assert results[0].verdict is Verdict.PASS


def test_r02_fail_no_rtl(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,1\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(2000.0, "rc_loss_in_air"),
                _radio_confirm(2500.0),
                '{"t_boot_ms": 1000, "type": "mode", "payload": {"name": "STABILIZE"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert results[0].verdict is Verdict.FAIL


def test_r02_fail_too_slow_mode(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,1\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(2000.0, "rc_loss_in_air"),
                _radio_confirm(2500.0),
                '{"t_boot_ms": 1000, "type": "mode", "payload": {"name": "STABILIZE"}}',
                '{"t_boot_ms": 40000, "type": "mode", "payload": {"name": "RTL"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert results[0].verdict is Verdict.FAIL


def test_r02_unconfirmed_fault(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,1\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(2000.0, "rc_loss_in_air"),
                '{"t_boot_ms": 1000, "type": "mode", "payload": {"name": "STABILIZE"}}',
                '{"t_boot_ms": 2100, "type": "mode", "payload": {"name": "RTL"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert results[0].verdict is Verdict.CANNOT_JUDGE
    assert "Fault not confirmed" in results[0].reason


def test_r02_missing_fault_event(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,1\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _radio_confirm(2500.0),
                '{"t_boot_ms": 2100, "type": "mode", "payload": {"name": "RTL"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert results[0].verdict is Verdict.CANNOT_JUDGE


def test_r02_precondition_fs_off(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,0\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(2000.0),
                _radio_confirm(2500.0),
                '{"t_boot_ms": 1000, "type": "mode", "payload": {"name": "STABILIZE"}}',
                '{"t_boot_ms": 2100, "type": "mode", "payload": {"name": "RTL"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert len(results) == 1
    assert results[0].verdict is Verdict.FAIL
    assert "precondition" in results[0].reason.lower() or "radio" in results[0].reason.lower()


def test_r01_pass_arming_refused(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r01_rc_loss_disarmed_blocks_arming.yaml")
    params = load_param_file(
        _write_param(tmp_path / "p.param", "FS_THR_ENABLE,1\nFS_OPTIONS,0\n")
    )
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(800.0, "rc_loss_while_disarmed"),
                _radio_confirm(810.0),
                '{"t_boot_ms": 920, "type": "statustext", "payload": {"text": "PreArm: Radio failsafe active"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert results[0].verdict is Verdict.PASS


def test_r03_battery_land(tmp_path: Path, repo_root: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r03_battery_low_triggers_land.yaml")
    params = load_param_file(_write_param(tmp_path / "p.param", "BATT_FS_LOW_ACT,1\n"))
    tl = load_jsonl(
        _write_jsonl(
            tmp_path / "t.jsonl",
            [
                _fault(3000.0, "battery_low"),
                '{"t_boot_ms": 3010, "type": "statustext", "payload": {"text": "Battery failsafe triggered"}}',
                '{"t_boot_ms": 2000, "type": "mode", "payload": {"name": "STABILIZE"}}',
                '{"t_boot_ms": 3200, "type": "mode", "payload": {"name": "LAND"}}',
            ],
        )
    )
    results = evaluate_rule(rule=rule, params=params, metadata=dict(MIN_COPTER_METADATA), timeline=tl)
    assert results[0].verdict is Verdict.PASS
