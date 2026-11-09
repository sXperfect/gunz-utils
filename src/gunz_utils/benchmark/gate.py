"""Multi-metric regression gate with validity requirements."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .policy import MetricDecision, MetricPolicy, evaluate_metric


@dataclass(frozen=True, slots=True)
class RegressionGate:
    """Aggregate decision for a performance comparison."""

    passed: bool
    decisions: tuple[MetricDecision, ...]
    warnings: tuple[str, ...]


def evaluate_regression_gate(
    baseline: Mapping[str, float],
    candidate: Mapping[str, float],
    policies: tuple[MetricPolicy, ...],
    *,
    warnings: tuple[str, ...] = (),
    require_comparable: bool = True,
) -> RegressionGate:
    """Evaluate multiple metrics and optionally fail on validity warnings.

    Parameters
    ----------
    baseline : Mapping[str, float]
        baseline parameter.
    candidate : Mapping[str, float]
        candidate parameter.
    policies : tuple[MetricPolicy, ...]
        policies parameter.
    warnings : tuple[str, ...]
        warnings parameter.
    require_comparable : bool
        require_comparable parameter.

    Returns
    -------
    RegressionGate
        The result of the operation.
    """
    if not isinstance(baseline, Mapping):
        raise TypeError(f"expected Mapping for baseline, got {type(baseline).__name__}")
    if not isinstance(candidate, Mapping):
        raise TypeError(f"expected Mapping for candidate, got {type(candidate).__name__}")
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
