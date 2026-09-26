"""Multi-metric regression gate with validity requirements."""

from __future__ import annotations

from dataclasses import dataclass

from .policy import MetricDecision, MetricPolicy, evaluate_metric


@dataclass(frozen=True)
class RegressionGate:
    """Aggregate decision for a performance comparison."""

    passed: bool
    decisions: tuple[MetricDecision, ...]
    warnings: tuple[str, ...]


def evaluate_regression_gate(
    baseline: dict[str, float],
    candidate: dict[str, float],
    policies: tuple[MetricPolicy, ...],
    *,
    warnings: tuple[str, ...] = (),
    require_comparable: bool = True,
) -> RegressionGate:
    """Evaluate multiple metrics and optionally fail on validity warnings."""
    decisions: list[MetricDecision] = []
    for policy in policies:
        if policy.name not in baseline or policy.name not in candidate:
            raise KeyError(f"missing metric required by policy: {policy.name}")
        decisions.append(
            evaluate_metric(
                baseline[policy.name],
                candidate[policy.name],
                policy,
            )
        )
    passed = all(item.passed for item in decisions)
    if require_comparable and warnings:
        passed = False
    return RegressionGate(passed, tuple(decisions), warnings)


__all__ = ["RegressionGate", "evaluate_regression_gate"]
