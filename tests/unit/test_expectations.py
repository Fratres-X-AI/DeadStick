from __future__ import annotations

import json
from pathlib import Path

import pytest

from deadstick.evaluate.expectations import (
    batt_low_modes_from_metadata,
    eval_simple_expr,
    rc_loss_modes_from_metadata,
)

from tests.helpers.metadata_samples import MIN_COPTER_METADATA


def test_eval_simple_expr_chained_compare() -> None:
    params = {"FS_THR_ENABLE": 1.0, "BATT_FS_LOW_ACT": 1.0}
    assert eval_simple_expr("FS_THR_ENABLE != 0 and BATT_FS_LOW_ACT != 0", params)


@pytest.fixture
def copter_metadata() -> dict:
    return MIN_COPTER_METADATA


def test_rc_loss_rtl_from_metadata(copter_metadata: dict) -> None:
    modes, err = rc_loss_modes_from_metadata(
        copter_metadata, {"FS_THR_ENABLE": 1.0, "FS_OPTIONS": 0.0}
    )
    assert err is None
    assert modes == ["RTL"]


def test_rc_loss_continue_auto_on_rc_cannot_judge(copter_metadata: dict) -> None:
    modes, err = rc_loss_modes_from_metadata(
        copter_metadata, {"FS_THR_ENABLE": 1.0, "FS_OPTIONS": 1.0}
    )
    assert modes is None
    assert err is not None and "auto" in err.lower()


def test_rc_loss_continue_guided_on_rc_cannot_judge(copter_metadata: dict) -> None:
    modes, err = rc_loss_modes_from_metadata(
        copter_metadata, {"FS_THR_ENABLE": 1.0, "FS_OPTIONS": 4.0}
    )
    assert modes is None
    assert err is not None and "guided" in err.lower()


@pytest.fixture
def copter_472_metadata(repo_root: Path) -> dict:
    path = repo_root / "metadata" / "Copter-4.7.2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_fs_thr_enable_maps_smartrtl_or_rtl_from_472(copter_472_metadata: dict) -> None:
    modes, err = rc_loss_modes_from_metadata(
        copter_472_metadata, {"FS_THR_ENABLE": 4.0, "FS_OPTIONS": 0.0}
    )
    assert err is None
    assert modes == ["SMART_RTL", "RTL"]


def test_batt_fs_low_act_brake_or_land_from_472(copter_472_metadata: dict) -> None:
    modes, err = batt_low_modes_from_metadata(
        copter_472_metadata, {"BATT_FS_LOW_ACT": 7.0}
    )
    assert err is None
    assert modes == ["BRAKE", "LAND"]


def test_batt_fs_low_act_terminate_cannot_judge(copter_472_metadata: dict) -> None:
    modes, err = batt_low_modes_from_metadata(
        copter_472_metadata, {"BATT_FS_LOW_ACT": 5.0}
    )
    assert modes is None
    assert err is not None and "Unmapped" in err and "Terminate" in err


def test_fs_options_gcs_auto_bit_does_not_block_rc_rule(copter_472_metadata: dict) -> None:
    modes, err = rc_loss_modes_from_metadata(
        copter_472_metadata, {"FS_THR_ENABLE": 1.0, "FS_OPTIONS": 2.0}
    )
    assert err is None
    assert modes == ["RTL"]
