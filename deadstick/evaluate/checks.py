from __future__ import annotations

import re
from typing import Any, Callable

from deadstick.evaluate.expectations import (
    batt_low_modes_from_metadata,
    normalize_statustext_pattern,
    rc_loss_action_modes,
    within_s_from_expr,
)
from deadstick.rules.schema import RuleFile, RuleKind
from deadstick.timeline.model import Timeline
from deadstick.verdict import Result, Verdict

CheckFn = Callable[..., Result]


def _resolve_within_s(payload: dict[str, Any], params: dict[str, float]) -> float:
    if "within_s_expr" in payload:
        return within_s_from_expr(str(payload["within_s_expr"]), params)
    w = payload.get("within_s")
    if isinstance(w, (int, float)):
        return float(w)
    if isinstance(w, str):
        return within_s_from_expr(w, params)
    raise TypeError("Expected within_s or within_s_expr in payload")


def _resolve_modes(
    payload: dict[str, Any], metadata: dict, params: dict[str, float]
) -> tuple[list[str] | None, str | None]:
    if "modes" in payload:
        raw = payload["modes"]
        if not isinstance(raw, list):
            raise TypeError("modes must be a list")
        return [str(m) for m in raw], None
    modes_from = payload.get("modes_from")
    if not modes_from:
        return None, "Expected modes or modes_from in payload."
    if modes_from == "expectations.rc_loss_action":
        return rc_loss_action_modes("expectations.rc_loss_action", metadata, params)
    if modes_from == "expectations.batt_low_action":
        return batt_low_modes_from_metadata(metadata, params)
    return None, f"Unknown modes_from {modes_from!r}"


def _anchor_ms(payload: dict[str, Any], timeline: Timeline, rule: RuleFile) -> float | None:
    from deadstick.evaluate.confirmation import infer_fault_inject_time

    return infer_fault_inject_time(timeline, rule=rule)


def check_expect_mode_within(
    *,
    rule_id: str,
    kind: RuleKind,
    rule: RuleFile,
    timeline: Timeline,
    metadata: dict,
    params: dict[str, float],
    payload: dict[str, Any],
) -> Result:
    modes, err = _resolve_modes(payload, metadata, params)
    if err:
        return Result(rule_id=rule_id, verdict=Verdict.CANNOT_JUDGE, reason=err)
    assert modes is not None
    anchor_ms = _anchor_ms(payload, timeline, rule)
    if anchor_ms is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.CANNOT_JUDGE,
            reason="expect_mode_within needs fault_injected in timeline.",
        )
    try:
        within_s = _resolve_within_s(payload, params)
    except TypeError as exc:
        return Result(rule_id=rule_id, verdict=Verdict.ERROR, reason=str(exc))
    t1 = anchor_ms + within_s * 1000.0
    for e in timeline.between(anchor_ms, t1):
        if e.type != "mode":
            continue
        name = str(e.payload.get("name", "")).strip().upper()
        if name.startswith("UNKNOWN_"):
            return Result(
                rule_id=rule_id,
                verdict=Verdict.CANNOT_JUDGE,
                reason=f"Mode {name!r} is not mapped from dataflash; cannot judge.",
            )
        if any(name == m.strip().upper() for m in modes):
            return Result(
                rule_id=rule_id,
                verdict=Verdict.PASS,
                reason=f"Observed mode {name} within {within_s}s after anchor.",
                evidence=[{"t_boot_ms": e.t_boot_ms, "mode": name}],
            )
    msg = f"No mode in {modes!r} within {within_s}s after {anchor_ms} ms."
    return Result(
        rule_id=rule_id,
        verdict=Verdict.FAIL if kind is RuleKind.requirement else Verdict.CANNOT_JUDGE,
        reason=msg,
    )


def check_expect_no_mode_change(
    *,
    rule_id: str,
    kind: RuleKind,
    rule: RuleFile,
    timeline: Timeline,
    metadata: dict,  # noqa: ARG001
    params: dict[str, float],  # noqa: ARG001
    payload: dict[str, Any],
) -> Result:
    start_ms = float(payload["start_ms"])
    end_ms = float(payload["end_ms"])
    m0 = timeline.mode_at(start_ms)
    m1 = timeline.mode_at(end_ms)
    if m0 is None or m1 is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.ERROR,
            reason="Could not resolve mode at window boundaries.",
        )
    for e in timeline.between(start_ms, end_ms):
        if e.type != "mode":
            continue
        name = str(e.payload.get("name", ""))
        if name != m0:
            msg = f"Mode changed from {m0!r} to {name!r} inside [{start_ms}, {end_ms}] ms."
            return Result(
                rule_id=rule_id,
                verdict=Verdict.FAIL if kind is RuleKind.requirement else Verdict.CANNOT_JUDGE,
                reason=msg,
                evidence=[{"t_boot_ms": e.t_boot_ms, "from": m0, "to": name}],
            )
    if m0 != m1:
        msg = f"Mode at end {m1!r} differs from start {m0!r} without intermediate mode events."
        return Result(
            rule_id=rule_id,
            verdict=Verdict.FAIL if kind is RuleKind.requirement else Verdict.CANNOT_JUDGE,
            reason=msg,
        )
    return Result(
        rule_id=rule_id,
        verdict=Verdict.PASS,
        reason=f"Mode remained {m0!r} for [{start_ms}, {end_ms}] ms.",
    )


def check_expect_alt_at_least(
    *,
    rule_id: str,
    kind: RuleKind,
    rule: RuleFile,
    timeline: Timeline,
    metadata: dict,  # noqa: ARG001
    params: dict[str, float],
    payload: dict[str, Any],
) -> Result:
    start_ms = float(payload["start_ms"])
    end_ms = float(payload["end_ms"])
    min_m = float(payload["min_m"])
    got = timeline.max_rel_alt_between(start_ms, end_ms)
    if got is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.ERROR,
            reason="No position/altitude samples in window.",
        )
    if got + 1e-6 >= min_m:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.PASS,
            reason=f"Max relative altitude {got:.3f} m >= {min_m:.3f} m.",
            evidence=[{"max_rel_alt_m": got}],
        )
    msg = f"Max relative altitude {got:.3f} m below required {min_m:.3f} m."
    return Result(
        rule_id=rule_id,
        verdict=Verdict.FAIL if kind is RuleKind.requirement else Verdict.CANNOT_JUDGE,
        reason=msg,
        evidence=[{"max_rel_alt_m": got}],
    )


def check_expect_statustext(
    *,
    rule_id: str,
    kind: RuleKind,
    rule: RuleFile,
    timeline: Timeline,
    metadata: dict,  # noqa: ARG001
    params: dict[str, float],
    payload: dict[str, Any],
) -> Result:
    anchor_ms = _anchor_ms(payload, timeline, rule)
    if anchor_ms is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.CANNOT_JUDGE,
            reason="expect_statustext needs fault_injected in timeline.",
        )
    try:
        within_s = _resolve_within_s(payload, params)
    except TypeError as exc:
        return Result(rule_id=rule_id, verdict=Verdict.ERROR, reason=str(exc))
    pat = normalize_statustext_pattern(str(payload["pattern"]))
    t1 = anchor_ms + within_s * 1000.0
    for e in timeline.between(anchor_ms, t1):
        if e.type != "statustext":
            continue
        text = str(e.payload.get("text", ""))
        if pat.search(text):
            return Result(
                rule_id=rule_id,
                verdict=Verdict.PASS,
                reason="Matching STATUSTEXT found.",
                evidence=[{"t_boot_ms": e.t_boot_ms, "text": text}],
            )
    msg = f"No STATUSTEXT matching {payload['pattern']!r} within {within_s}s after {anchor_ms} ms."
    return Result(
        rule_id=rule_id,
        verdict=Verdict.FAIL if kind is RuleKind.requirement else Verdict.CANNOT_JUDGE,
        reason=msg,
    )


def check_expect_arming_refused(
    *,
    rule_id: str,
    kind: RuleKind,
    rule: RuleFile,
    timeline: Timeline,
    metadata: dict,  # noqa: ARG001
    params: dict[str, float],
    payload: dict[str, Any],
) -> Result:
    anchor_ms = _anchor_ms(payload, timeline, rule)
    if anchor_ms is None:
        return Result(
            rule_id=rule_id,
            verdict=Verdict.CANNOT_JUDGE,
            reason="expect_arming_refused needs fault_injected in timeline.",
        )
    try:
        within_s = _resolve_within_s(payload, params)
    except TypeError as exc:
        return Result(rule_id=rule_id, verdict=Verdict.ERROR, reason=str(exc))
    t1 = anchor_ms + within_s * 1000.0
    pat_s = payload.get("pattern")
    if pat_s is None:
        pat = re.compile(r"arm.*(denied|fail|reject)|prearm|not arm", re.IGNORECASE)
    else:
        pat = normalize_statustext_pattern(str(pat_s))
    for e in timeline.between(anchor_ms, t1):
        if e.type != "statustext":
            continue
        text = str(e.payload.get("text", ""))
        if pat.search(text):
            return Result(
                rule_id=rule_id,
                verdict=Verdict.PASS,
                reason="Arming refusal indicated in STATUSTEXT.",
                evidence=[{"t_boot_ms": e.t_boot_ms, "text": text}],
            )
    msg = f"No arming-refusal STATUSTEXT within {within_s}s after {anchor_ms} ms."
    return Result(
        rule_id=rule_id,
        verdict=Verdict.FAIL if kind is RuleKind.requirement else Verdict.CANNOT_JUDGE,
        reason=msg,
    )


CHECK_REGISTRY: dict[str, CheckFn] = {
    "expect_mode_within": check_expect_mode_within,
    "expect_no_mode_change": check_expect_no_mode_change,
    "expect_alt_at_least": check_expect_alt_at_least,
    "expect_statustext": check_expect_statustext,
    "expect_arming_refused": check_expect_arming_refused,
}
