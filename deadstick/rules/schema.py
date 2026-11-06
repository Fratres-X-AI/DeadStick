from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

IMPLEMENTED_CHECKS = frozenset(
    {
        "expect_mode_within",
        "expect_no_mode_change",
        "expect_alt_at_least",
        "expect_statustext",
        "expect_arming_refused",
    }
)


class RuleKind(str, Enum):
    requirement = "requirement"
    conformance = "conformance"


class Precondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expr: str
    reason_if_not: str


class ScenarioStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def flatten(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if len(data) != 1:
            raise ValueError("Each scenario step must be a single-key object")
        key = next(iter(data))
        val = data[key]
        if val is None:
            val = {}
        if not isinstance(val, dict):
            raise ValueError(f"Step {key} must map to an object")
        return {"step": key, "args": val}


class ConfirmFaultAnyOf(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statustext: str | None = None


class ConfirmFault(BaseModel):
    model_config = ConfigDict(extra="forbid")

    any_of: list[ConfirmFaultAnyOf]
    within_s: float


class ExpectCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_anchor_ms(self) -> ExpectCheck:
        if "anchor_ms" in self.payload:
            raise ValueError('expect blocks must not use "anchor_ms"; anchoring comes from fault_injected / PARM only')
        return self

    @model_validator(mode="before")
    @classmethod
    def flatten(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "check" in data:
            c = data["check"]
            rest = {k: v for k, v in data.items() if k != "check"}
            return {"check": c, "payload": rest}
        return data


class RuleFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    say: str
    kind: RuleKind
    vehicle: Literal["copter"] = "copter"
    firmware_min: str = "Copter-4.7.0"
    requires_params: list[str] = Field(default_factory=list)
    precondition: Precondition | None = None
    scenario: list[ScenarioStep]
    confirm_fault: ConfirmFault | None = None
    expect: list[ExpectCheck] = Field(default_factory=list)
    repeats: int = 1

    @model_validator(mode="after")
    def check_expectations(self) -> RuleFile:
        for e in self.expect:
            if e.check not in IMPLEMENTED_CHECKS:
                raise ValueError(f'ERROR: no check implemented for "{e.check}" (rule {self.id})')
        return self


def load_rule_yaml(text: str) -> RuleFile:
    import yaml

    data = yaml.safe_load(text)
    return TypeAdapter(RuleFile).validate_python(data)
