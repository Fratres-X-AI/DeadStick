from __future__ import annotations

from pathlib import Path


def test_harness_does_not_use_rc_channels_override(repo_root: Path) -> None:
    sim_dir = repo_root / "deadstick" / "sim"
    needles = ("rc_channels_override", "RC_CHANNELS_OVERRIDE")
    for path in sorted(sim_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for n in needles:
            assert n.lower() not in lower, f"{path} must not mention {n}"
