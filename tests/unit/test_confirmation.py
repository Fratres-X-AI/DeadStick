from __future__ import annotations

from pathlib import Path

from deadstick.evaluate.confirmation import evaluate_fault_gate, fault_confirmed
from deadstick.rules.schema import ConfirmFault, ConfirmFaultAnyOf
from deadstick.timeline.jsonl import load_jsonl
from deadstick.timeline.model import Timeline, TimelineEvent
from deadstick.verdict import Verdict


def test_fault_confirmed_statustext(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    p.write_text(
        "\n".join(
            [
                '{"t_boot_ms": 1000, "type": "fault_injected", "payload": {}}',
                '{"t_boot_ms": 1100, "type": "statustext", "payload": {"text": "Radio failsafe triggered"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tl = load_jsonl(p)
    spec = ConfirmFault(
        any_of=[ConfirmFaultAnyOf(statustext="(?i)radio.*failsafe")],
        within_s=5.0,
    )
    ok, _ = fault_confirmed(timeline=tl, spec=spec, fault_t_ms=1000.0)
    assert ok


def test_evaluate_gate_missing_fault() -> None:
    tl = Timeline(
        [
            TimelineEvent(1000, "statustext", {"text": "Radio failsafe triggered"}),
        ]
    )
    spec = ConfirmFault(
        any_of=[ConfirmFaultAnyOf(statustext="radio")],
        within_s=5.0,
    )
    r = evaluate_fault_gate(rule_id="x", spec=spec, timeline=tl, fault_t_ms=None)
    assert r is not None
    assert r.verdict is Verdict.CANNOT_JUDGE
