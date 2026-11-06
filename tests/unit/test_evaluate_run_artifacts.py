from __future__ import annotations

from pathlib import Path

from deadstick.param_file import load_param_file
from deadstick.rules.loader import load_rule
from deadstick.sim.scenario_engine import evaluate_run_artifacts
from deadstick.verdict import Verdict

from tests.helpers.metadata_samples import MIN_COPTER_METADATA


def test_evaluate_run_artifacts_no_inputs_errors(repo_root: Path) -> None:
    rule = load_rule(
        repo_root / "rules" / "copter" / "r01_rc_loss_disarmed_blocks_arming.yaml"
    )
    verdict, rows = evaluate_run_artifacts(
        rule=rule,
        metadata=dict(MIN_COPTER_METADATA),
        vehicle_params={},
        file_params={},
        dataflash_path=None,
        timeline_jsonl_path=None,
        harness_error=None,
    )
    assert verdict is Verdict.ERROR
    assert rows and "no dataflash log produced" in rows[0].reason


def test_no_bin_nonempty_jsonl_errors(repo_root: Path, tmp_path: Path) -> None:
    rule = load_rule(repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml")
    (tmp_path / "p.param").write_text(
        "FS_THR_ENABLE,1\nFS_OPTIONS,0\nRC_FS_TIMEOUT,2\n", encoding="utf-8"
    )
    params = load_param_file(tmp_path / "p.param")

    jsonl = tmp_path / "t.jsonl"
    jsonl.write_text(
        '{"t_boot_ms": 1, "type": "mode", "payload": {"name": "GUIDED"}}\n',
        encoding="utf-8",
    )

    verdict, rows = evaluate_run_artifacts(
        rule=rule,
        metadata=dict(MIN_COPTER_METADATA),
        vehicle_params=params,
        file_params=params,
        dataflash_path=None,
        timeline_jsonl_path=jsonl,
        harness_error=None,
    )
    assert verdict is Verdict.ERROR
    assert rows and "no dataflash log produced" in rows[0].reason
