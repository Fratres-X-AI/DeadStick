from __future__ import annotations

from pathlib import Path

import pytest

from deadstick.evaluate.runner import evaluate_rule
from deadstick.metadata import load_metadata
from deadstick.param_file import load_param_file
from deadstick.rules.loader import load_rule
from deadstick.timeline.dataflash import bin_to_timeline
from deadstick.verdict import Verdict

from tests.helpers.metadata_samples import MIN_COPTER_METADATA


def _meta(repo_root: Path) -> dict:
    files = sorted((repo_root / "metadata").glob("Copter-*.json"))
    if not files:
        return dict(MIN_COPTER_METADATA)
    return load_metadata(files[0])


@pytest.mark.needs_pod_log
def test_r01_pass_bin(repo_root: Path) -> None:
    bin_path = repo_root / "tests" / "fixtures" / "dataflash" / "r01_pass.BIN"
    if not bin_path.is_file():
        pytest.skip("no r01_pass.BIN fixture")

    rule = load_rule(
        repo_root / "rules" / "copter" / "r01_rc_loss_disarmed_blocks_arming.yaml"
    )
    params = load_param_file(repo_root / "tests" / "fixtures" / "params" / "default.param")
    meta = _meta(repo_root)
    tl = bin_to_timeline(bin_path, params=params)
    results = evaluate_rule(rule=rule, params=params, metadata=meta, timeline=tl)
    assert results and results[0].verdict is Verdict.PASS


@pytest.mark.needs_pod_log
def test_r02_fail_fs_off_bin(repo_root: Path) -> None:
    bin_path = repo_root / "tests" / "fixtures" / "dataflash" / "r02_fail_fs_off.BIN"
    param_path = repo_root / "tests" / "fixtures" / "params" / "bad" / "fs_thr_off.param"
    if not bin_path.is_file():
        pytest.skip("no r02_fail_fs_off.BIN fixture")

    rule = load_rule(
        repo_root / "rules" / "copter" / "r02_rc_loss_rtl_when_configured.yaml"
    )
    params = load_param_file(param_path)
    meta = _meta(repo_root)
    tl = bin_to_timeline(bin_path, params=params)
    results = evaluate_rule(rule=rule, params=params, metadata=meta, timeline=tl)
    assert results and results[0].verdict is Verdict.FAIL
