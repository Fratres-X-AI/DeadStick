from __future__ import annotations

from pathlib import Path

import pytest

from deadstick.timeline.dataflash import bin_to_timeline


@pytest.mark.needs_pod_log
def test_bin_reader_smoke(repo_root: Path) -> None:
    """Unskip when the pod commits a small sample under tests/fixtures/dataflash/."""
    p = repo_root / "tests" / "fixtures" / "dataflash" / "sample.bin"
    if not p.is_file():
        pytest.skip("no pod .BIN fixture (tests/fixtures/dataflash/sample.bin)")

    t = bin_to_timeline(p)
    assert isinstance(t.events, list)
