from __future__ import annotations

from pathlib import Path

import pytest

from deadstick.timeline.dataflash import bin_to_timeline


_CANDIDATE_BINS = ("r01_pass.BIN", "r02_fail_fs_off.BIN", "sample.bin")


@pytest.mark.needs_pod_log
def test_bin_reader_smoke(repo_root: Path) -> None:
    """Runs when the pod commits a sample under tests/fixtures/dataflash/."""
    for name in _CANDIDATE_BINS:
        p = repo_root / "tests" / "fixtures" / "dataflash" / name
        if p.is_file():
            t = bin_to_timeline(p, params={})
            assert isinstance(t.events, list)
            return
    pytest.skip("no pod .BIN fixture in tests/fixtures/dataflash/")
