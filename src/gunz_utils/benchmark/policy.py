"""Configurable performance-regression policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MetricPolicy:
    """Threshold policy for one metric."""

    name: str
    direction: Literal["lower", "higher"]
    relative_threshold: float | None = None
    absolute_threshold: float | None = None


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
