from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    # tests/conftest.py -> repository root is parents[1]
    return Path(__file__).resolve().parents[1]
