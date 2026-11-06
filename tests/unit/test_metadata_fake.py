from __future__ import annotations

import json
from pathlib import Path

import pytest

from deadstick.metadata import assert_not_fake_metadata, load_metadata


def test_fake_filename_refused(tmp_path: Path) -> None:
    p = tmp_path / "FAKE_x.json"
    p.write_text(json.dumps({"parameters": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing"):
        assert_not_fake_metadata(p, load_metadata(p))


def test_fake_json_flag_refused(tmp_path: Path) -> None:
    p = tmp_path / "realname.json"
    p.write_text(json.dumps({"fake": True, "parameters": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing"):
        assert_not_fake_metadata(p, load_metadata(p))


def test_real_named_metadata_ok(tmp_path: Path) -> None:
    p = tmp_path / "copter_param_metadata.json"
    data = {"parameters": {"FS_THR_ENABLE": {"values": {"1": "RTL"}}}}
    p.write_text(json.dumps(data), encoding="utf-8")
    assert_not_fake_metadata(p, load_metadata(p))
