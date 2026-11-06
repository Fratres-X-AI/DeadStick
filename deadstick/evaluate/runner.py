from __future__ import annotations

from pathlib import Path
from typing import Any

from deadstick.evaluate.checks import CHECK_REGISTRY
from deadstick.evaluate.confirmation import evaluate_fault_gate, infer_fault_inject_time
from deadstick.evaluate.expectations import apply_precondition
from deadstick.metadata import assert_not_fake_metadata, load_metadata
from deadstick.param_file import load_param_file
from deadstick.rules.loader import load_rule
from deadstick.rules.schema import RuleFile
from deadstick.timeline.jsonl import load_jsonl
from deadstick.timeline.model import Timeline
from deadstick.verdict import Result, Verdict


def _timeline_from_log(log: Path) -> Timeline:
    suf = log.suffix.lower()
    if suf == ".jsonl":
        return load_jsonl(log)
    if suf == ".bin":
        from deadstick.timeline.dataflash import bin_to_timeline

        return bin_to_timeline(log)
    raise ValueError(f"Unsupported log type {log.suffix!r} (use .jsonl or .bin)")


def evaluate_rule(
    *,
    rule: RuleFile,
    params: dict[str, float],
    metadata: dict[str, Any],
    timeline: Timeline,
) -> list[Result]:
    results: list[Result] = []

    missing = [p for p in rule.requires_params if p not in params]
    if missing:
        results.append(
            Result(
                rule_id=rule.id,
                verdict=Verdict.CANNOT_JUDGE,
                reason=f"Parameter file missing keys required by the rule: {missing}",
            )
        )
        return results

    if rule.precondition:
        pre = apply_precondition(
            rule_id=rule.id,
            kind=rule.kind,
            precondition_expr=rule.precondition.expr,
            reason_if_not=rule.precondition.reason_if_not,
            params=params,
        )
        if pre is not None:
            results.append(pre)
            return results

    fault_ms = infer_fault_inject_time(timeline)
    gate = evaluate_fault_gate(
        rule_id=rule.id,
        spec=rule.confirm_fault,
        timeline=timeline,
        fault_t_ms=fault_ms,
    )
    if gate is not None:
        results.append(gate)
        return results

    for exp in rule.expect:
        fn = CHECK_REGISTRY.get(exp.check)
        if fn is None:
            results.append(
                Result(
                    rule_id=rule.id,
                    verdict=Verdict.ERROR,
                    reason=f'No check registered for "{exp.check}"',
                )
            )
            continue
        try:
            r = fn(
                rule_id=rule.id,
                kind=rule.kind,
                timeline=timeline,
                metadata=metadata,
                params=params,
                payload=exp.payload,
            )
        except Exception as exc:  # noqa: BLE001
            r = Result(
                rule_id=rule.id,
                verdict=Verdict.ERROR,
                reason=f'Check "{exp.check}" raised: {exc}',
            )
        results.append(r)
        if r.verdict is Verdict.FAIL:
            break

    return results


def run_from_paths(
    *,
    rule_path: Path,
    param_path: Path,
    metadata_path: Path,
    log_path: Path,
) -> list[Result]:
    rule = load_rule(rule_path)
    params = load_param_file(param_path)
    meta = load_metadata(metadata_path)
    assert_not_fake_metadata(metadata_path, meta)
    timeline = _timeline_from_log(log_path)
    return evaluate_rule(rule=rule, params=params, metadata=meta, timeline=timeline)
