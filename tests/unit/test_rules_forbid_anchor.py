from __future__ import annotations

from pathlib import Path

import pytest

from deadstick.rules.loader import load_rule


def test_repo_rules_must_not_use_anchor_ms(repo_root: Path) -> None:
    p = repo_root / "rules" / "copter" / "r01_rc_loss_disarmed_blocks_arming.yaml"
    load_rule(p)

    bad = repo_root / "rules" / "copter" / "_test_forbid_anchor_ms.yaml"
    bad.write_text(
        "\n".join(
            [
                "id: x",
                "say: test",
                "kind: conformance",
                "scenario:",
                "  - inject_fault:",
                "      kind: rc_loss_while_disarmed",
                "confirm_fault:",
                "  any_of:",
                "    - statustext: x",
                "  within_s: 5",
                "expect:",
                "  - check: expect_statustext",
                "    anchor_ms: 1",
                "    pattern: foo",
                "    within_s: 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="fault_injected"):
            load_rule(bad)
    finally:
        bad.unlink(missing_ok=True)
