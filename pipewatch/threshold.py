"""Threshold-based alerting rules for numeric metrics."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ThresholdOp(str, Enum):
    GT = "gt"   # greater than
    GTE = "gte" # greater than or equal
    LT = "lt"   # less than
    LTE = "lte" # less than or equal
    EQ = "eq"   # equal


@dataclass
class ThresholdRule:
    job: str
    metric: str
    op: ThresholdOp
    value: float
    severity: str = "warning"
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "job": self.job,
            "metric": self.metric,
            "op": self.op.value,
            "value": self.value,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class ThresholdViolation:
    rule: ThresholdRule
    actual: float
    message: str = field(init=False)

    def __post_init__(self) -> None:
        self.message = (
            f"[{self.rule.severity.upper()}] {self.rule.job}/{self.rule.metric} "
            f"{self.rule.op.value} {self.rule.value} (actual={self.actual})"
        )

    def to_dict(self) -> dict:
        return {
            "job": self.rule.job,
            "metric": self.rule.metric,
            "op": self.rule.op.value,
            "threshold": self.rule.value,
            "actual": self.actual,
            "severity": self.rule.severity,
            "message": self.message,
        }


_OPS = {
    ThresholdOp.GT:  lambda a, b: a > b,
    ThresholdOp.GTE: lambda a, b: a >= b,
    ThresholdOp.LT:  lambda a, b: a < b,
    ThresholdOp.LTE: lambda a, b: a <= b,
    ThresholdOp.EQ:  lambda a, b: a == b,
}


def evaluate_threshold(rule: ThresholdRule, actual: float) -> Optional[ThresholdViolation]:
    """Return a ThresholdViolation if *actual* breaches *rule*, else None."""
    if _OPS[rule.op](actual, rule.value):
        return ThresholdViolation(rule=rule, actual=actual)
    return None


def evaluate_all(
    rules: list[ThresholdRule],
    samples: dict[str, dict[str, float]],  # {job: {metric: value}}
) -> list[ThresholdViolation]:
    """Evaluate every rule against the provided sample map."""
    violations: list[ThresholdViolation] = []
    for rule in rules:
        job_samples = samples.get(rule.job, {})
        if rule.metric not in job_samples:
            continue
        v = evaluate_threshold(rule, job_samples[rule.metric])
        if v is not None:
            violations.append(v)
    return violations
