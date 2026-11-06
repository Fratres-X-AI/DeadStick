from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    CANNOT_JUDGE = "CANNOT_JUDGE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Result:
    rule_id: str
    verdict: Verdict
    reason: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
