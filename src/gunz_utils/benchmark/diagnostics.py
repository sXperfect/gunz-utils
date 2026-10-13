"""Benchmark stability and comparability diagnostics."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .result import BenchmarkResult


@dataclass(frozen=True)
class StabilityReport:
    """Noise diagnostics for one benchmark result."""

    coefficient_of_variation: float
    relative_range: float
    outlier_count: int
    stable: bool
    warnings: tuple[str, ...]


def analyze_stability(
    result: BenchmarkResult,
    *,
    max_cv: float = 0.05,
    max_relative_range: float = 0.20,
) -> StabilityReport:
    """Detect noisy timing distributions using robust simple diagnostics.

    Parameters
    ----------
    result : BenchmarkResult
        result parameter.
    max_cv : float
        max_cv parameter.
    max_relative_range : float
        max_relative_range parameter.

    Returns
    -------
    StabilityReport
        The result of the operation.
    """
    for name, value in (
        ("max_cv", max_cv),
        ("max_relative_range", max_relative_range),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value < 0
        ):
            raise ValueError(
                f"{name} must be a finite non-negative number"
            )

    values = list(result.samples)
    if not values:
        raise ValueError("benchmark samples must not be empty")
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
        for value in values
    ):
        raise ValueError(
            "benchmark samples must be finite non-negative numbers"
        )
    mean = statistics.fmean(values)
    cv = 0.0 if mean == 0 else statistics.pstdev(values) / mean
    median = statistics.median(values)
    spread = max(values) - min(values)
    if median == 0:
        # A zero median with non-zero spread means division by zero, so the
        # relative range is effectively infinite. Reporting 0.0 here would
        # mask a large spread as "no variance", so surface it as infinity
        # (which then trips the range warning). All-zero samples have no
        # spread and correctly report 0.0.
        relative_range = math.inf if spread > 0 else 0.0
    else:
        relative_range = spread / median
    quartiles = statistics.quantiles(values, n=4) if len(values) >= 4 else None
    outliers = 0
    if quartiles is not None:
        q1, _, q3 = quartiles
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = sum(value < low or value > high for value in values)
    warnings: list[str] = []
    if cv > max_cv:
        warnings.append(f"coefficient of variation is high ({cv:.2%})")
    if relative_range > max_relative_range:
        if math.isinf(relative_range):
            warnings.append("sample range is high")
        else:
            warnings.append(f"sample range is high ({relative_range:.2%})")
    if outliers:
        warnings.append(f"{outliers} timing outlier(s) detected")
    return StabilityReport(
        coefficient_of_variation=cv,
        relative_range=relative_range,
        outlier_count=outliers,
        stable=not warnings,
        warnings=tuple(warnings),
    )


def comparability_warnings(
    baseline: BenchmarkResult,
    candidate: BenchmarkResult,
) -> tuple[str, ...]:
    """Describe environment differences that can invalidate comparisons.

    Parameters
    ----------
    baseline : BenchmarkResult
        baseline parameter.
    candidate : BenchmarkResult
        candidate parameter.

    Returns
    -------
    tuple[str, ...]
        The result of the operation.
    """
    warnings: list[str] = []
    left, right = baseline.system, candidate.system
    if left.machine != right.machine:
        warnings.append(f"machine differs: {left.machine!r} vs {right.machine!r}")
    if left.processor != right.processor:
        warnings.append("processor differs")
    if left.cpu_count != right.cpu_count:
        warnings.append(f"CPU count differs: {left.cpu_count} vs {right.cpu_count}")
    if left.python != right.python:
        warnings.append(f"Python differs: {left.python} vs {right.python}")
    if left.platform != right.platform:
        warnings.append("platform/kernel description differs")
    return tuple(warnings)


__all__ = [
    "StabilityReport",
    "analyze_stability",
    "comparability_warnings",
]
