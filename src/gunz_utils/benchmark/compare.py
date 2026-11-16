"""Benchmark regression comparison."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .result import BenchmarkResult


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    """Relative change between baseline and candidate timing statistics."""

    median_change: float
    p95_change: float
    mean_change: float
    regressed: bool


def _finite_non_negative(
    name: str,
    value: float,
) -> float:
    """_finite_non_negative() function.

    Parameters
    ----------
    name : str
        name parameter.
    value : float
        value parameter.

    Returns
    -------
    float
        The result of the operation.
    """
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


def _change(
    before: float,
    after: float,
) -> float:
    """_change() function.

    Parameters
    ----------
    before : float
        before parameter.
    after : float
        after parameter.

    Returns
    -------
    float
        The result of the operation.
    """
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
    """Compare timing results against configurable relative regression limits.

    Parameters
    ----------
    baseline : BenchmarkResult
        baseline parameter.
    candidate : BenchmarkResult
        candidate parameter.
    median_threshold : float
        median_threshold parameter.
    p95_threshold : float
        p95_threshold parameter.

    Returns
    -------
    BenchmarkComparison
        The result of the operation.
    """
    median_threshold = _finite_non_negative(
        "median_threshold",
        median_threshold,
    )
    p95_threshold = _finite_non_negative(
        "p95_threshold",
        p95_threshold,
    )
    if not isinstance(baseline, BenchmarkResult):
        raise TypeError(
            f"expected BenchmarkResult for baseline, got {type(baseline).__name__}")
    if not isinstance(candidate, BenchmarkResult):
        raise TypeError(
            f"expected BenchmarkResult for candidate, got {type(candidate).__name__}")
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


def detect_regression(
    baseline: float,
    current: float,
    threshold_pct: float = 5.0,
) -> bool:
    """Return True if candidate duration is higher than baseline by > threshold_pct."""
    if baseline <= 0:
        return current > 0
    pct_change = ((current - baseline) / baseline) * 100.0
    return pct_change > threshold_pct


def compare_benchmarks(
    baseline: dict[str, Any] | BenchmarkResult,
    current: dict[str, Any] | BenchmarkResult,
    *,
    threshold_pct: float = 5.0,
) -> dict[str, Any]:
    """Compare benchmark metrics and determine regression status."""
    if isinstance(baseline, BenchmarkResult):
        b_dict = {
    "mean": baseline.stats.mean,
    "median": baseline.stats.median,
     "p95": baseline.stats.p95}
    else:
        b_dict = dict(baseline)

    if isinstance(current, BenchmarkResult):
        c_dict = {
    "mean": current.stats.mean,
    "median": current.stats.median,
     "p95": current.stats.p95}
    else:
        c_dict = dict(current)

    metrics_comparison: dict[str, Any] = {}
    any_regressed = False

    for key, b_val in b_dict.items():
        if key in c_dict and isinstance(
    b_val, (int, float)) and isinstance(
        c_dict[key], (int, float)):
            c_val = c_dict[key]
            delta = c_val - b_val
            pct = 0.0 if b_val == 0 else (delta / b_val) * 100.0
            reg = detect_regression(
    float(b_val),
    float(c_val),
     threshold_pct=threshold_pct)
            if reg:
                any_regressed = True
            metrics_comparison[key] = {
                "baseline": b_val,
                "current": c_val,
                "delta": delta,
                "percent_change": pct,
                "regressed": reg,
            }

    return {
        "metrics": metrics_comparison,
        "regressed": any_regressed,
        "threshold_pct": threshold_pct,
    }


def generate_markdown_comparison_table(
    comparison_results: Sequence[dict[str, Any]],
) -> str:
    """Generate GitHub-Flavored Markdown table summarizing benchmark comparisons."""
    headers = ["Benchmark", "Baseline", "Current", "Delta", "% Change", "Status"]
    rows: list[str] = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for comp in comparison_results:
        name = str(comp.get("name", "benchmark"))
        b_val = comp.get("baseline", 0.0)
        c_val = comp.get("current", 0.0)
        delta = comp.get("delta", c_val - b_val)
        pct = comp.get("percent_change", 0.0)
        reg = comp.get("regressed", False)
        status = "**REGRESSED**" if reg else "PASSED"
        pct_str = f"{pct:+.2f}%"
        delta_str = f"{delta:+.4f}"
        rows.append(
            f"| {name} | {b_val:.4f} | {c_val:.4f} "
                f"| {delta_str} | {pct_str} | {status} |"
        )
    return "\n".join(rows)


__all__ = [
    "BenchmarkComparison",
    "compare_benchmarks",
    "compare_results",
    "detect_regression",
    "generate_markdown_comparison_table",
]
