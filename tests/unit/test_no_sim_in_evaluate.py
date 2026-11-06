from __future__ import annotations

import ast
from pathlib import Path


def test_evaluate_package_does_not_import_sim() -> None:
    """The evaluator must not import the simulator harness."""
    root = Path(__file__).resolve().parents[2] / "deadstick" / "evaluate"
    for py in root.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                "deadstick.sim"
            ):
                raise AssertionError(f"{py.name} imports {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("deadstick.sim"):
                        raise AssertionError(f"{py.name} imports {alias.name}")
