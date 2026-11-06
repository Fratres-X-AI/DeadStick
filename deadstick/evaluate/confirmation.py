from __future__ import annotations

import re
from typing import Any

from deadstick.rules.schema import ConfirmFault, ConfirmFaultAnyOf
from deadstick.timeline.model import Timeline, TimelineEvent
from deadstick.verdict import Result, Verdict

def _match_statustext(pat: str, text: str) -> bool:
    return re.search(pat, text, re.IGNORECASE) is not None


def _err_matches(entry: dict[str, Any], want: dict[str, Any]) -> bool:
    for k, v in want.items():
        if k not in entry:
            return False
        if entry.get(k) != v:
            return False
    return True


def _any_predicate(
    pred: ConfirmFaultAnyOf,
    events: list[TimelineEvent],
) -> bool:
    if pred.statustext is not None:
        for e in events:
            if e.type != "statustext":
                continue
            if _match_statustext(pred.statustext, str(e.payload.get("text", ""))):
                return True
    if pred.log_err is not None:
        want = dict(pred.log_err)
        for e in events:
            if e.type != "err":
                continue
            pl = e.payload
            entry: dict[str, Any] = {
                "subsys": pl.get("subsys"),
                "ecode": pl.get("ecode"),
            }
            if _err_matches(want, entry):
                return True
    return False


def fault_confirmed(
    *,
    timeline: Timeline,
    spec: ConfirmFault,
    fault_t_ms: float,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    True if within fault_t_ms .. fault_t_ms + within_s*1000 some any_of branch matches.
    """
    t0 = fault_t_ms
    t1 = fault_t_ms + spec.within_s * 1000.0
    window = timeline.between(t0, t1)
    evidence: list[dict[str, Any]] = []
    for branch in spec.any_of:
        if _any_predicate(branch, window):
            evidence.append({"branch": branch.model_dump(), "window_ms": [t0, t1]})
            return True, evidence
    return False, []


def evaluate_fault_gate(
    *,
    rule_id: str,
    spec: ConfirmFault | None,
    timeline: Timeline,
    fault_t_ms: float | None,
) -> Result | None:
    """
    If no spec, no gate. If fault time unknown, CANNOT_JUDGE.
    If not confirmed in window, CANNOT_JUDGE per plan §0 rule 10.
    """
    if spec is None:
        return None
    if fault_t_ms is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.CANNOT_JUDGE,
            reason="Fault confirmation required but no fault_injected event in timeline.",
        )
    ok, ev = fault_confirmed(timeline=timeline, spec=spec, fault_t_ms=fault_t_ms)
    if ok:
        return None
    return Result(
        rule_id=rule_id,
        verdict=Verdict.CANNOT_JUDGE,
        reason=(
            "Fault not confirmed by vehicle within "
            f"{spec.within_s}s after inject (no matching ERR/STATUSTEXT)."
        ),
        evidence=ev,
    )


def infer_fault_inject_time(timeline: Timeline) -> float | None:
    ev = timeline.first("fault_injected")
    return float(ev.t_boot_ms) if ev is not None else None
