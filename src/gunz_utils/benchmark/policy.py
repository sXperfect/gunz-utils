"""Configurable performance-regression policy."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal


@dataclass(frozen=True)
class MetricPolicy:
    """Threshold policy for one metric."""

    name: str
    direction: Literal["lower", "higher"]
    relative_threshold: float | None = None
    absolute_threshold: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("metric name must be a non-empty string")
        if self.direction not in {"lower", "higher"}:
            raise ValueError("direction must be 'lower' or 'higher'")
        for name, value in (
            ("relative_threshold", self.relative_threshold),
            ("absolute_threshold", self.absolute_threshold),
        ):
            if value is None:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value < 0
            ):
                raise ValueError(
                    f"{name} must be a finite non-negative number or None"
                )


@dataclass(frozen=True)
class MetricDecision:
    name: str
    baseline: float
    candidate: float
    relative_change: float
    passed: bool


def evaluate_metric(
    baseline: float,
    candidate: float,
    policy: MetricPolicy,
) -> MetricDecision:
    """Evaluate one candidate metric against its regression policy."""
    for name, value in (
        ("baseline", baseline),
        ("candidate", candidate),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"{name} must be a finite number")

    relative = (
        0.0
        if baseline == candidate
        else float("inf")
        if baseline == 0
        else (candidate - baseline) / abs(baseline)
    )
    degradation = relative if policy.direction == "lower" else -relative
    passed = True
    if policy.relative_threshold is not None:
        passed = passed and degradation <= policy.relative_threshold
    if policy.absolute_threshold is not None:
        absolute_degradation = (
            candidate - baseline
            if policy.direction == "lower"
            else baseline - candidate
        )
        passed = passed and absolute_degradation <= policy.absolute_threshold
    return MetricDecision(
        name=policy.name,
        baseline=baseline,
        candidate=candidate,
        relative_change=relative,
        passed=passed,
    )


__all__ = ["MetricDecision", "MetricPolicy", "evaluate_metric"]
