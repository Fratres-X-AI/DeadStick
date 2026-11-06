from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from deadstick.rules.schema import ConfirmFault, ConfirmFaultAnyOf

if TYPE_CHECKING:
    from deadstick.rules.schema import RuleFile

from deadstick.timeline.model import Timeline, TimelineEvent
from deadstick.verdict import Result, Verdict


def _match_statustext(pat: str, text: str) -> bool:
    return re.search(pat, text, re.IGNORECASE) is not None


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
    If not confirmed in window, CANNOT_JUDGE (expectation checks are skipped).
    """
    if spec is None:
        return None
    if fault_t_ms is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.CANNOT_JUDGE,
            reason=(
                "Fault confirmation required but fault inject time is unknown "
                "(no fault_injected in timeline; for .BIN use PARM SIM_RC_FAIL / SIM_BATT_VOLTAGE)."
            ),
        )
    ok, ev = fault_confirmed(timeline=timeline, spec=spec, fault_t_ms=fault_t_ms)
    if ok:
        return None
    return Result(
        rule_id=rule_id,
        verdict=Verdict.CANNOT_JUDGE,
        reason=(f"Fault not confirmed by vehicle within {spec.within_s}s after inject (no matching STATUSTEXT)."),
        evidence=ev,
    )


def infer_fault_inject_time(timeline: Timeline, rule: "RuleFile | None" = None) -> float | None:
    """
    Fault time from the first matching fault_injected event.
    PARM-derived events use kinds ``rc_loss`` / ``battery_low``; rule YAML uses longer names.
    """
    inject_kinds: list[str] = []
    if rule is not None:
        for st in rule.scenario:
            if st.step == "inject_fault":
                inject_kinds.append(str(st.args.get("kind", "")).lower())

    def _matches(ev: TimelineEvent) -> bool:
        ek = str(ev.payload.get("kind", "")).lower()
        if not inject_kinds:
            return True
        for want in inject_kinds:
            if "battery" in want and "battery" in ek:
                return True
            if ("rc" in want or "loss" in want) and "rc" in ek:
                return True
        return False

    for ev in timeline.events:
        if ev.type != "fault_injected":
            continue
        if not inject_kinds:
            return float(ev.t_boot_ms)
        if _matches(ev):
            return float(ev.t_boot_ms)
    return None
