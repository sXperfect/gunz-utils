"""Pristine-state variant experiments and numeric metric comparisons."""

from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any, Callable


@dataclass(frozen=True)
class VariantResult:
    """Metrics or error produced by one independently initialized variant."""

    name: str
    metrics: dict[str, Any]
    error: str | None = None


def run_variant_matrix(
    setup: Callable[[], Any],
    run: Callable[[Any, dict[str, Any]], dict[str, Any]],
    variants: dict[str, dict[str, Any]],
    *,
    baseline: str = "baseline",
) -> dict[str, Any]:
    """Run configuration variants from independently rebuilt state.

    Parameters
    ----------
    setup : Callable[[], Any]
        Factory called once per variant to create pristine mutable state.
    run : Callable[[Any, dict[str, Any]], dict[str, Any]]
        Variant function receiving the fresh state and an independent deep
        copy of the variant configuration. It must return a metric mapping.
    variants : dict[str, dict[str, Any]]
        Named variant configurations.
    baseline : str, optional
        Variant used as the metric-comparison reference.

    Returns
    -------
    dict[str, Any]
        Baseline name, per-variant results, and baseline-relative comparisons
        for variants that completed successfully.

    Raises
    ------
    KeyError
        If the named baseline is absent.

    Notes
    -----
    Exceptions are captured per variant by type name only so arbitrary
    exception text cannot leak secrets into reports. The setup factory is
    always called separately,
    preventing mutable state from leaking between variants.
    """
    if baseline not in variants:
        raise KeyError(f"baseline variant {baseline!r} is missing")

    results: dict[str, VariantResult] = {}
    for name, config in variants.items():
        try:
            state = setup()
            metrics = dict(
                run(
                    state,
                    copy.deepcopy(config),
                )
            )
            results[name] = VariantResult(
                name=name,
                metrics=metrics,
            )
        except Exception as exc:
            results[name] = VariantResult(
                name=name,
                metrics={},
                error=type(exc).__name__,
            )

    baseline_result = results[baseline]
    comparisons: dict[str, dict[str, dict[str, Any]]] = {}
    if baseline_result.error is None:
        for name, result in results.items():
            if name == baseline or result.error is not None:
                continue
            comparisons[name] = compare_numeric_metrics(
                baseline_result.metrics,
                result.metrics,
            )

    return {
        "baseline": baseline,
        "results": results,
        "comparisons": comparisons,
    }


def compare_numeric_metrics(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Compare shared numeric metrics while retaining structural differences.

    Booleans are treated as categorical rather than numeric, even though bool
    is a subclass of int in Python.
    """
    keys = sorted(set(baseline) | set(candidate))
    result: dict[str, dict[str, Any]] = {}

    for key in keys:
        if key not in baseline:
            result[key] = {"missing_baseline": True}
            continue
        if key not in candidate:
            result[key] = {"missing_candidate": True}
            continue

        left = baseline[key]
        right = candidate[key]
        if (
            isinstance(left, bool)
            or isinstance(right, bool)
            or not isinstance(left, (int, float))
            or not isinstance(right, (int, float))
        ):
            result[key] = {
                "numeric": False,
                "equal": left == right,
                "baseline": left,
                "candidate": right,
            }
            continue

        if isinstance(left, int) and isinstance(right, int):
            delta = right - left
            result[key] = {
                "numeric": True,
                "baseline": left,
                "candidate": right,
                "finite": True,
                "delta": delta,
                "relative_delta": (
                    delta / abs(left)
                    if left != 0
                    else None
                ),
            }
            continue

        left_value = float(left)
        right_value = float(right)
        delta = right_value - left_value
        result[key] = {
            "numeric": True,
            "baseline": left_value,
            "candidate": right_value,
            "finite": (
                math.isfinite(left_value)
                and math.isfinite(right_value)
            ),
            "delta": delta,
            "relative_delta": (
                delta / abs(left_value)
                if left_value != 0 and math.isfinite(delta)
                else None
            ),
        }

    return result


def metric_improvement(
    matrix: dict[str, Any],
    *,
    variant: str,
    metric: str,
    direction: str = "lower",
    minimum_relative_improvement: float = 0.0,
) -> dict[str, Any]:
    """Evaluate whether one variant changes a numeric metric as requested.

    Parameters
    ----------
    matrix : dict[str, Any]
        Result returned by :func:`run_variant_matrix`.
    variant : str
        Candidate variant name.
    metric : str
        Numeric metric name.
    direction : {"lower", "higher"}, optional
        Direction considered an improvement.
    minimum_relative_improvement : float, optional
        Required relative improvement, expressed as a non-negative fraction.

    Returns
    -------
    dict[str, Any]
        Support flag and, when available, relative improvement and compared
        metric values.

    Raises
    ------
    ValueError
        If the direction is invalid or the threshold is negative.

    Notes
    -----
    This reports operational evidence that an intervention changed one metric.
    It does not establish that the intervention is the unique cause.
    """
    if direction not in {"lower", "higher"}:
        raise ValueError("direction must be lower or higher")
    if minimum_relative_improvement < 0:
        raise ValueError("minimum_relative_improvement must be non-negative")

    comparison = matrix.get("comparisons", {}).get(variant, {}).get(metric)
    if not comparison or not comparison.get("numeric"):
        return {
            "supported": False,
            "reason": "metric comparison unavailable",
        }
    if not comparison.get("finite"):
        return {
            "supported": False,
            "reason": "metric comparison is non-finite",
        }

    baseline = comparison["baseline"]
    candidate = comparison["candidate"]
    scale = max(abs(baseline), 1e-12)
    relative_improvement = (
        (baseline - candidate) / scale
        if direction == "lower"
        else (candidate - baseline) / scale
    )
    return {
        "supported": (
            relative_improvement >= minimum_relative_improvement
        ),
        "relative_improvement": relative_improvement,
        "baseline": baseline,
        "candidate": candidate,
        "direction": direction,
    }


__all__ = [
    "VariantResult",
    "compare_numeric_metrics",
    "metric_improvement",
    "parameter_grid",
    "run_variant_matrix",
]



def parameter_grid(
    factors: Mapping[str, Sequence[Any]],
) -> list[dict[str, Any]]:
    """Return the Cartesian product of named factor values.

    Parameters
    ----------
    factors : Mapping[str, Sequence[Any]]
        Factor names mapped to candidate values.

    Returns
    -------
    list[dict[str, Any]]
        Parameter combinations in mapping/value order. An empty factor mapping
        produces one empty combination.

    Raises
    ------
    ValueError
        If a factor name is empty or any factor has no candidate values.
    """
    names = list(factors)
    for name in names:
        if not isinstance(name, str) or not name:
            raise ValueError(
                "factor names must be non-empty strings"
            )
        if not factors[name]:
            raise ValueError(
                f"factor {name!r} must contain at least one value"
            )

    return [
        dict(
            zip(
                names,
                values,
                strict=True,
            )
        )
        for values in itertools.product(
            *(factors[name] for name in names)
        )
    ]
