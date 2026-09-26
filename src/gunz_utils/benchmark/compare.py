"""Benchmark regression comparison."""

from __future__ import annotations

from dataclasses import dataclass

from .result import BenchmarkResult


@dataclass(frozen=True)
class BenchmarkComparison:
    """Relative change between baseline and candidate timing statistics."""

    median_change: float
    p95_change: float
    mean_change: float
    regressed: bool


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
    median = _change(baseline.stats.median, candidate.stats.median)
    p95 = _change(baseline.stats.p95, candidate.stats.p95)
    mean = _change(baseline.stats.mean, candidate.stats.mean)
    return BenchmarkComparison(
        median_change=median,
        p95_change=p95,
        mean_change=mean,
        regressed=median > median_threshold or p95 > p95_threshold,
    )


__all__ = ["BenchmarkComparison", "compare_results"]
