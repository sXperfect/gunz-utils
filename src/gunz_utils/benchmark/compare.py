"""Benchmark regression comparison."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .result import BenchmarkResult


@dataclass(frozen=True)
class BenchmarkComparison:
    """Relative change between baseline and candidate timing statistics."""

    median_change: float
    p95_change: float
    mean_change: float
    regressed: bool


def _finite_non_negative(name: str, value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ValueError(
            f"{name} must be a finite non-negative number"
        )
    return float(value)


def _change(before: float, after: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else float("inf")
    return (after - before) / before


def compare_results(
    baseline: BenchmarkResult,
    candidate: BenchmarkResult,
    *,
    median_threshold: float = 0.05,
    p95_threshold: float = 0.10,
) -> BenchmarkComparison:
    """Compare timing results against configurable relative regression limits."""
    median_threshold = _finite_non_negative(
        "median_threshold",
        median_threshold,
    )
    p95_threshold = _finite_non_negative(
        "p95_threshold",
        p95_threshold,
    )
    before_median = _finite_non_negative(
        "baseline median",
        baseline.stats.median,
    )
    after_median = _finite_non_negative(
        "candidate median",
        candidate.stats.median,
    )
    before_p95 = _finite_non_negative(
        "baseline p95",
        baseline.stats.p95,
    )
    after_p95 = _finite_non_negative(
        "candidate p95",
        candidate.stats.p95,
    )
    before_mean = _finite_non_negative(
        "baseline mean",
        baseline.stats.mean,
    )
    after_mean = _finite_non_negative(
        "candidate mean",
        candidate.stats.mean,
    )
    median = _change(before_median, after_median)
    p95 = _change(before_p95, after_p95)
    mean = _change(before_mean, after_mean)
    return BenchmarkComparison(
        median_change=median,
        p95_change=p95,
        mean_change=mean,
        regressed=median > median_threshold or p95 > p95_threshold,
    )


__all__ = ["BenchmarkComparison", "compare_results"]
