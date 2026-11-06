from __future__ import annotations

import ast
import re
from typing import Any

from deadstick.metadata import bitmask_bits_set, param_entry
from deadstick.rules.schema import RuleKind
from deadstick.verdict import Result, Verdict


def eval_simple_expr(expr: str, params: dict[str, float]) -> bool:
    """
    Safe-ish evaluator for preconditions like FS_THR_ENABLE != 0.
    Only names, comparisons, and bool ops.
    """

    def _eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.BoolOp):
            vals = [_eval_node(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(vals)
            if isinstance(node.op, ast.Or):
                return any(vals)
            raise ValueError("unsupported bool op")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not bool(_eval_node(node.operand))
        if isinstance(node, ast.Compare):
            left = _eval_node(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = _eval_node(right_node)
                if isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.Gt):
                    ok = left > right
                elif isinstance(op, ast.GtE):
                    ok = left >= right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                elif isinstance(op, ast.LtE):
                    ok = left <= right
                else:
                    raise ValueError("unsupported comparison")
                if not ok:
                    return False
                left = right
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return float(_eval_node(node.left)) + float(_eval_node(node.right))
        if isinstance(node, ast.Name):
            if node.id not in params:
                raise KeyError(node.id)
            return float(params[node.id])
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"unsupported ast {type(node)}")

    tree = ast.parse(expr, mode="eval")
    return bool(_eval_node(tree))


def within_s_from_expr(expr: str, params: dict[str, float]) -> float:
    tree = ast.parse(expr.strip(), mode="eval")

    class V(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802
            if node.id not in params:
                raise KeyError(node.id)
            return ast.copy_location(ast.Constant(float(params[node.id])), node)

        def visit_Expression(self, node: ast.Expression) -> ast.AST:  # noqa: N802
            return ast.Expression(self.visit(node.body))

    fixed = V().visit(tree)
    ast.fix_missing_locations(fixed)
    code = compile(fixed, "<within_s_expr>", "eval")
    return float(eval(code, {"__builtins__": {}}, {}))


def apply_precondition(
    *,
    rule_id: str,
    kind: RuleKind,
    precondition_expr: str | None,
    reason_if_not: str | None,
    params: dict[str, float],
) -> Result | None:
    if not precondition_expr:
        return None
    try:
        ok = eval_simple_expr(precondition_expr, params)
    except Exception as exc:  # noqa: BLE001
        return Result(
            rule_id=rule_id,
            verdict=Verdict.ERROR,
            reason=f"Could not evaluate precondition: {exc}",
        )
    if ok:
        return None
    msg = reason_if_not or "Precondition not met."
    if kind is RuleKind.requirement:
        return Result(rule_id=rule_id, verdict=Verdict.FAIL, reason=msg)
    return Result(rule_id=rule_id, verdict=Verdict.CANNOT_JUDGE, reason=msg)


def fs_thr_disabled_gate(
    *, rule_id: str, kind: RuleKind, params: dict[str, float]
) -> Result | None:
    if "FS_THR_ENABLE" not in params:
        return None
    if float(params["FS_THR_ENABLE"]) != 0.0:
        return None
    msg = "Radio failsafe is disabled in this parameter file (FS_THR_ENABLE = 0)."
    if kind is RuleKind.requirement:
        return Result(rule_id=rule_id, verdict=Verdict.FAIL, reason=msg)
    return Result(rule_id=rule_id, verdict=Verdict.CANNOT_JUDGE, reason=msg)


def rc_loss_modes_from_metadata(
    metadata: dict[str, Any], params: dict[str, float]
) -> tuple[list[str] | None, str | None]:
    thr = params.get("FS_THR_ENABLE")
    if thr == 0.0:
        return None, "FS_THR_ENABLE is 0 — handled by precondition gate."

    fsopt = int(params.get("FS_OPTIONS", 0.0))
    # bitmask in fake metadata uses descriptive keys; bits from ArduPilot
    meta_fsopt = param_entry(metadata, "FS_OPTIONS")
    if isinstance(meta_fsopt, dict) and isinstance(meta_fsopt.get("bitmask"), dict):
        bm = meta_fsopt["bitmask"]
        bits = bitmask_bits_set(fsopt, bm)
        entries: list[tuple[int, str]] = []
        sample_k = next(iter(bm.keys()), "")
        if str(sample_k).isdigit():
            for idx_s, label in bm.items():
                entries.append((int(idx_s), str(label)))
        else:
            for label, idx in bm.items():
                entries.append((int(idx), str(label)))

        for _bi, label in entries:
            if _bi not in bits:
                continue
            low = label.lower()
            if "continue" not in low:
                continue
            if "auto" in low:
                return None, (
                    "FS_OPTIONS has continue-in-auto set; expected outcome is continue "
                    "(no RTL). This bench has no Auto rule yet — CANNOT_JUDGE for rc_loss_action."
                )
            if "guided" in low:
                return None, (
                    "FS_OPTIONS has continue-in-guided set; expected outcome is continue in GUIDED "
                    "(no RTL). This bench does not model that path — CANNOT_JUDGE for rc_loss_action."
                )

    ent = param_entry(metadata, "FS_THR_ENABLE")
    if not ent:
        return None, "FS_THR_ENABLE not described in firmware metadata."
    val = str(int(float(thr))) if thr is not None else None
    values = ent.get("values")
    if not isinstance(values, dict) or val is None:
        return None, "FS_THR_ENABLE values missing in metadata."
    label = str(values.get(val, "")).lower()
    if "rtl" in label:
        return ["RTL"], None
    if "land" in label or "landing" in label:
        return ["LAND"], None
    return None, f"FS_THR_ENABLE value {val} meaning not recognized in metadata."


def rc_loss_action_modes(
    modes_from: str, metadata: dict[str, Any], params: dict[str, float]
) -> tuple[list[str] | None, str | None]:
    if modes_from == "expectations.rc_loss_action":
        return rc_loss_modes_from_metadata(metadata, params)
    return None, f"Unknown modes_from {modes_from!r}"


def batt_low_modes_from_metadata(
    metadata: dict[str, Any], params: dict[str, float]
) -> tuple[list[str] | None, str | None]:
    act = params.get("BATT_FS_LOW_ACT")
    if act is None:
        return None, "BATT_FS_LOW_ACT not in parameter file."
    ent = param_entry(metadata, "BATT_FS_LOW_ACT")
    if not ent:
        return None, "BATT_FS_LOW_ACT not described in firmware metadata."
    values = ent.get("values")
    if not isinstance(values, dict):
        return None, "BATT_FS_LOW_ACT values missing in metadata."
    val = str(int(float(act)))
    label = str(values.get(val, "")).lower()
    if "land" in label:
        return ["LAND"], None
    if "rtl" in label:
        return ["RTL"], None
    if val == "0" or "none" in label:
        return None, "Battery low action is none/disabled — requirement FAIL handled elsewhere."
    return None, f"BATT_FS_LOW_ACT value {val} meaning not recognized."


def normalize_statustext_pattern(pat: str) -> re.Pattern[str]:
    return re.compile(pat, re.IGNORECASE)
