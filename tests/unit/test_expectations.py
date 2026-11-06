from __future__ import annotations

import pytest

from deadstick.evaluate.expectations import eval_simple_expr, rc_loss_modes_from_metadata

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
