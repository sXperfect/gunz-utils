"""Pristine-state variant experiments and numeric metric comparisons."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import copy
import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VariantResult:
    """Metrics or error produced by one independently initialized variant."""

    name: str
    metrics: dict[str, Any]
    error: str | None = None


class ExperimentMatrix(dict[str, Any]):
    """Execution matrix produced by run_variant_matrix."""

    @property
    def baseline(self) -> str:
        """Return the name of the baseline variant."""
        return self["baseline"]

    @property
    def results(self) -> dict[str, VariantResult]:
        """Return per-variant execution results."""
        return self["results"]

    @property
    def comparisons(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return baseline-relative metric comparisons."""
        return self["comparisons"]

    def succeeded_variants(self) -> tuple[str, ...]:
        """Return names of variants that completed without error."""
        return tuple(name for name, res in self.results.items() if res.error is None)

    def failed_variants(self) -> tuple[str, ...]:
        """Return names of variants that encountered errors."""
        return tuple(name for name, res in self.results.items() if res.error is not None)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary copy of the matrix."""
        return dict(self)


def run_variant_matrix(
    setup: Callable[[], Any],
    run: Callable[[Any, dict[str, Any]], dict[str, Any]],
    variants: Mapping[str, dict[str, Any]],
    *,
    baseline: str = "baseline",
) -> ExperimentMatrix:
    """Run configuration variants from independently rebuilt state.

    Parameters
    ----------
    setup : Callable[[], Any]
        Factory called once per variant to create pristine mutable state.
    run : Callable[[Any, dict[str, Any]], dict[str, Any]]
        Variant function receiving the fresh state and an independent deep
        copy of the variant configuration. It must return a metric mapping.
    variants : Mapping[str, dict[str, Any]]
        Named variant configurations.
    baseline : str, optional
        Variant used as the metric-comparison reference.

    Returns
    -------
    ExperimentMatrix
        Baseline name, per-variant results, and baseline-relative comparisons
        for variants that completed successfully.

    Raises
    ------
    KeyError
        If the named baseline is absent.
    TypeError
        If setup or run is not callable, or variants is not a Mapping.
    ValueError
        If variants mapping is empty.

    Notes
    -----
    Exceptions are captured per variant by type name only so arbitrary
    exception text cannot leak secrets into reports. The setup factory is
    always called separately,
    preventing mutable state from leaking between variants.
    """
    if not isinstance(variants, Mapping):
        raise TypeError("variants must be a Mapping")
    if not variants:
        raise ValueError("variants mapping must not be empty")
    if not callable(setup):
        raise TypeError("setup must be callable")
    if not callable(run):
        raise TypeError("run must be callable")
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

    return ExperimentMatrix(
        {
            "baseline": baseline,
            "results": results,
            "comparisons": comparisons,
        }
    )


def compare_numeric_metrics(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Compare shared numeric metrics while retaining structural differences.

    Booleans are treated as categorical rather than numeric, even though bool
    is a subclass of int in Python.
    """
    if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
        raise TypeError("baseline and candidate must be mappings")
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
            try:
                rel = delta / abs(left) if left != 0 else None
            except OverflowError:
                rel = None
            result[key] = {
                "numeric": True,
                "baseline": left,
                "candidate": right,
                "finite": True,
                "delta": delta,
                "relative_delta": rel,
            }
            continue

        try:
            left_value = float(left)
            right_value = float(right)
            delta_f = right_value - left_value
        except OverflowError:
            result[key] = {
                "numeric": True,
                "baseline": left,
                "candidate": right,
                "finite": False,
                "delta": None,
                "relative_delta": None,
            }
            continue
        result[key] = {
            "numeric": True,
            "baseline": left_value,
            "candidate": right_value,
            "finite": (
                math.isfinite(left_value)
                and math.isfinite(right_value)
            ),
            "delta": delta_f,
            "relative_delta": (
                delta_f / abs(left_value)
                if left_value != 0 and math.isfinite(delta_f)
                else None
            ),
        }

    return result


def metric_improvement(
    matrix: Mapping[str, Any],
    *,
    variant: str,
    metric: str,
    direction: str = "lower",
    minimum_relative_improvement: float = 0.0,
) -> dict[str, Any]:
    """Evaluate whether one variant changes a numeric metric as requested.

    Parameters
    ----------
    matrix : Mapping[str, Any]
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
    TypeError
        If matrix is not a Mapping, or variant/metric is not a string.
    ValueError
        If the direction is invalid, the threshold is negative, or variant/metric is empty.

    Notes
    -----
    This reports operational evidence that an intervention changed one metric.
    It does not establish that the intervention is the unique cause.
    """
    if not isinstance(matrix, Mapping):
        raise TypeError("matrix must be a Mapping")
    if not isinstance(variant, str):
        raise TypeError("variant must be a string")
    if not variant.strip():
        raise ValueError("variant must be a non-empty string")
    if not isinstance(metric, str):
        raise TypeError("metric must be a string")
    if not metric.strip():
        raise ValueError("metric must be a non-empty string")

    if direction not in {"lower", "higher"}:
        raise ValueError("direction must be lower or higher")
    if isinstance(minimum_relative_improvement, bool) or not isinstance(
        minimum_relative_improvement, (int, float)
    ):
        raise TypeError("minimum_relative_improvement must be a real number")
    if (
        not math.isfinite(minimum_relative_improvement)
        or minimum_relative_improvement < 0
    ):
        raise ValueError(
            "minimum_relative_improvement must be a finite non-negative number"
        )

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
    diff = (baseline - candidate) if direction == "lower" else (candidate - baseline)
    try:
        relative_improvement = diff / scale
    except OverflowError:
        relative_improvement = float("inf") if diff > 0 else float("-inf")

    if not math.isfinite(relative_improvement):
        return {
            "supported": False,
            "reason": "metric comparison is non-finite",
        }

    return {
        "supported": (
            relative_improvement >= minimum_relative_improvement
        ),
        "relative_improvement": relative_improvement,
        "baseline": baseline,
        "candidate": candidate,
        "direction": direction,
    }


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
    TypeError
        If factors is not a Mapping, or a factor's values is a string or not iterable.
    ValueError
        If a factor name is empty or any factor has no candidate values.
    """
    if not isinstance(factors, Mapping):
        raise TypeError("factors must be a Mapping")
    names = list(factors)
    factor_values: dict[str, tuple[Any, ...]] = {}
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "factor names must be non-empty strings"
            )
        val = factors[name]
        if isinstance(val, (str, bytes, bytearray)):
            raise TypeError(
                f"factor {name!r} values must be a sequence of values, not {type(val).__name__}"
            )
        try:
            seq = tuple(val)
        except TypeError as exc:
            raise TypeError(f"factor {name!r} values must be iterable") from exc
        if not seq:
            raise ValueError(
                f"factor {name!r} must contain at least one value"
            )
        factor_values[name] = seq

    return [
        dict(
            zip(
                names,
                values,
                strict=True,
            )
        )
        for values in itertools.product(
            *(factor_values[name] for name in names)
        )
    ]


__all__ = [
    "ExperimentMatrix",
    "VariantResult",
    "compare_numeric_metrics",
    "metric_improvement",
    "parameter_grid",
    "run_variant_matrix",
]
