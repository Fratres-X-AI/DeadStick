from __future__ import annotations

from pathlib import Path

from deadstick.rules.schema import RuleFile, load_rule_yaml


def load_rule(path: Path) -> RuleFile:
    return load_rule_yaml(path.read_text(encoding="utf-8"))
