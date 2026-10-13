"""Benchmark regression comparison."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
from dataclasses import dataclass

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .result import BenchmarkResult


@dataclass(frozen=True)
class BenchmarkComparison:
    """Relative change between baseline and candidate timing statistics.

    A change of ``None`` represents an effectively infinite increase (a
    non-zero candidate over a zero baseline), which serializes to ``null``
    in JSON rather than a non-standard ``Infinity`` token.
    """

    median_change: float | None
    p95_change: float | None
    mean_change: float | None
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
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{name} must be a finite non-negative number"
        )
    try:
        value_float = float(value)
    except OverflowError:
        #? A finite value that is not float-representable (e.g. 10**400) must
        #? surface as the documented ValueError, not leak an internal
        #? OverflowError.
        raise ValueError(
            f"{name} must be a finite non-negative number"
        ) from None
    if not math.isfinite(value_float) or value < 0:
        raise ValueError(
            f"{name} must be a finite non-negative number"
        )
    return value_float


def _change(
    before: float,
    after: float,
) -> float | None:
    """_change() function.

    Parameters
    ----------
    before : float
        before parameter.
    after : float
        after parameter.

    Returns
    -------
    float | None
        The relative change, or ``None`` when it is effectively infinite (a
        non-zero ``after`` over a zero ``before``). ``None`` serializes to
        ``null`` in JSON, keeping CLI output standards-compliant.
    """
    if before == 0:
        return 0.0 if after == 0 else None
    return (after - before) / before


def _exceeds_threshold(
    change: float | None,
    threshold: float,
) -> bool:
    """Whether a relative change counts as a regression.

    An infinite change (``None``) is an unbounded increase and always counts
    as a regression.
    """
    return change is None or change > threshold


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
        regressed=_exceeds_threshold(median, median_threshold)
        or _exceeds_threshold(p95, p95_threshold),
    )


__all__ = ["BenchmarkComparison", "compare_results"]
