from __future__ import annotations

from deadstick.evaluate.confirmation import infer_fault_inject_time
from deadstick.timeline.model import Timeline, TimelineEvent


def test_infer_fault_time_first_matching() -> None:
    tl = Timeline([TimelineEvent(5000.0, "fault_injected", {"kind": "rc_loss"})])
    assert infer_fault_inject_time(tl) == 5000.0
