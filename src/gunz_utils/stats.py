"""Small dependency-free statistical helpers for repeated experiments."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib
import math
import random
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from numbers import Real
from statistics import fmean, median, pstdev, pvariance, stdev
from typing import Any, TypeVar

try:
    _accel = importlib.import_module("._accel", package=__package__)
    _accel_update_running_stats: Callable[
        ..., tuple[int, float, float, float, float, float]
    ] | None = getattr(_accel, "update_running_stats", None)
    _accel_fast_summary: Callable[..., dict[str, Any]] | None = getattr(
        _accel, "fast_summary", None
    )
except (ImportError, AttributeError):  # pragma: no cover
    _accel_update_running_stats = None
    _accel_fast_summary = None

T = TypeVar("T")


@dataclass(frozen=True)
class BootstrapMeanCI:
    """Bootstrap confidence interval for an arithmetic mean."""

    mean: float
    low: float
    high: float
    confidence: float
    samples: int
    observations: int


@dataclass(frozen=True)
class PairedEffect:
    """Mean paired difference and standardized within-pair effect."""

    mean_difference: float
    standard_deviation: float
    standardized_effect: float | None
    observations: int


@dataclass(frozen=True)
class SummaryStats:
    """Summary statistics for a sample distribution."""

    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    variance: float
    stdev: float
    coefficient_of_variation: float | None
    mad: float
    percentiles: Mapping[float, float]
    outlier_indices: tuple[int, ...]



def _finite_values(
    values: Iterable[float],
    *,
    name: str,
) -> list[float]:
    """Convert values to finite floats and require at least one observation.

    Parameters
    ----------
    values : Iterable[float]
        values parameter.
    name : str
        name parameter.

    Returns
    -------
    list[float]
        The result of the operation.
    """
    raw = list(values)
    if not raw:
        raise ValueError(f"{name} must not be empty")
    if any(
        isinstance(value, bool) or not isinstance(value, Real)
        for value in raw
    ):
        raise ValueError(f"{name} must contain only real numeric values")
    converted = [float(value) for value in raw]
    if not all(math.isfinite(value) for value in converted):
        raise ValueError(f"{name} must contain only finite values")
    return converted


def bootstrap_mean_ci(
    values: Iterable[float],
    *,
    confidence: float = 0.95,
    samples: int = 2000,
    seed: int = 0,
) -> BootstrapMeanCI:
    """Estimate a percentile bootstrap confidence interval for the mean.

    Parameters
    ----------
    values : Iterable[float]
        Finite observations.
    confidence : float, optional
        Confidence mass strictly between 0 and 1.
    samples : int, optional
        Number of bootstrap resamples. Must be positive.
    seed : int, optional
        Deterministic pseudo-random seed.

    Returns
    -------
    BootstrapMeanCI
        Observed mean and percentile confidence interval.

    Notes
    -----
    This is a basic percentile bootstrap. It does not perform BCa correction or
    account for dependence between observations. Runtime is proportional to
    samples times observations, plus sorting the samples; inputs and resample
    count are caller-selected budgets without a hard memory or time limit.
    """
    observations = _finite_values(
        values,
        name="values",
    )
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, Real)
        or not math.isfinite(float(confidence))
        or not 0.0 < float(confidence) < 1.0
    ):
        raise ValueError(
            "confidence must be a finite number strictly between 0 and 1"
        )
    if (
        isinstance(samples, bool)
        or not isinstance(samples, int)
        or samples < 1
    ):
        raise ValueError("samples must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    confidence = float(confidence)
    rng = random.Random(seed)
    count = len(observations)
    estimates = [
        fmean(
            rng.choice(observations)
            for _ in range(count)
        )
        for _ in range(samples)
    ]
    estimates.sort()

    alpha = (1.0 - confidence) / 2.0
    low_index = max(
        0,
        min(
            samples - 1,
            math.floor(alpha * samples),
        ),
    )
    high_index = max(
        0,
        min(
            samples - 1,
            math.ceil((1.0 - alpha) * samples) - 1,
        ),
    )
    return BootstrapMeanCI(
        mean=fmean(observations),
        low=estimates[low_index],
        high=estimates[high_index],
        confidence=confidence,
        samples=samples,
        observations=count,
    )


def paired_effect(
    left: Iterable[float],
    right: Iterable[float],
) -> PairedEffect:
    """Summarize paired differences and their standardized effect.

    The standardized effect is the mean of pairwise differences divided by the
    sample standard deviation of those differences, commonly called Cohen's dz.
    It is None when fewer than two pairs are available or the paired-difference
    variance is zero.

    Parameters
    ----------
    left : Iterable[float]
        First finite paired observations.
    right : Iterable[float]
        Second finite paired observations.

    Returns
    -------
    PairedEffect
        Mean difference, sample standard deviation, standardized effect and
        observation count.

    Raises
    ------
    ValueError
        If samples are empty, unequal in length, contain non-finite values, or
        a pairwise difference is not representable as a finite float.
    OverflowError
        If the standardized effect is not representable as a finite float.
    """
    left_values = _finite_values(
        left,
        name="left",
    )
    right_values = _finite_values(
        right,
        name="right",
    )
    if len(left_values) != len(right_values):
        raise ValueError("paired samples must have equal length")

    differences = [
        left_value - right_value
        for left_value, right_value in zip(
            left_values,
            right_values,
            strict=True,
        )
    ]
    if not all(math.isfinite(value) for value in differences):
        raise ValueError(
            "paired differences must be representable as finite floats"
        )
    center = fmean(differences)
    if len(differences) < 2:
        return PairedEffect(
            mean_difference=center,
            standard_deviation=0.0,
            standardized_effect=None,
            observations=1,
        )

    standard_deviation = stdev(differences)
    standardized_effect = (
        center / standard_deviation
        if standard_deviation
        else None
    )
    if (
        standardized_effect is not None
        and not math.isfinite(standardized_effect)
    ):
        raise OverflowError(
            "standardized effect exceeds finite float range"
        )
    return PairedEffect(
        mean_difference=center,
        standard_deviation=standard_deviation,
        standardized_effect=standardized_effect,
        observations=len(differences),
    )





@dataclass(frozen=True)
class NormalMeanSummary:
    """Arithmetic mean, sample deviation, and z-based confidence interval."""

    observations: int
    mean: float
    standard_deviation: float
    low: float
    high: float
    confidence_z: float


def normal_mean_summary(
    values: Iterable[float],
    *,
    confidence_z: float = 1.96,
) -> NormalMeanSummary:
    """Summarize replicates with a normal-approximation mean interval.

    Parameters
    ----------
    values : Iterable[float]
        Finite replicate observations.
    confidence_z : float, optional
        Non-negative finite z multiplier. 1.96 corresponds approximately to a
        95 percent interval under the normal approximation.

    Returns
    -------
    NormalMeanSummary
        Count, mean, sample standard deviation, and interval bounds.

    Raises
    ------
    OverflowError
        If the interval cannot be represented using finite floats.

    Notes
    -----
    This is a fast descriptive normal approximation, not a bootstrap or
    Student-t interval. Use bootstrap_mean_ci when distributional assumptions
    are undesirable.
    """
    observations = _finite_values(
        values,
        name="values",
    )
    if (
        isinstance(confidence_z, bool)
        or not isinstance(confidence_z, Real)
        or not math.isfinite(float(confidence_z))
        or confidence_z < 0
    ):
        raise ValueError(
            "confidence_z must be a non-negative finite number"
        )
    confidence_z = float(confidence_z)

    center = fmean(observations)
    count = len(observations)
    if count == 1:
        return NormalMeanSummary(
            observations=1,
            mean=center,
            standard_deviation=0.0,
            low=center,
            high=center,
            confidence_z=confidence_z,
        )

    standard_deviation = stdev(observations)
    margin = (
        confidence_z
        * standard_deviation
        / math.sqrt(count)
    )
    low = center - margin
    high = center + margin
    if not all(
        math.isfinite(value)
        for value in (
            standard_deviation,
            margin,
            low,
            high,
        )
    ):
        raise OverflowError(
            "normal-mean interval exceeds finite float range"
        )
    return NormalMeanSummary(
        observations=count,
        mean=center,
        standard_deviation=standard_deviation,
        low=low,
        high=high,
        confidence_z=confidence_z,
    )


def _percentile_presorted(
    ordered: Sequence[float],
    q: float,
) -> float:
    """Compute percentile for presorted sequence using linear interpolation."""
    n = len(ordered)
    if n == 1:
        return ordered[0]

    position = (n - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]

    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def percentile(
    values: Sequence[float],
    q: float,
) -> float:
    """Compute quantile/percentile for sample sequence using linear interpolation.

    Parameters
    ----------
    values : Sequence[float]
        Sequence of finite numeric values.
    q : float
        Quantile between 0.0 and 1.0 inclusive.

    Returns
    -------
    float
        Interpolated quantile value.
    """
    if (
        isinstance(q, bool)
        or not isinstance(q, (int, float))
        or not math.isfinite(q)
        or not 0.0 <= q <= 1.0
    ):
        raise ValueError("percentile q must be finite and between 0 and 1")

    data = _finite_values(values, name="percentile")
    ordered = sorted(data)
    return _percentile_presorted(ordered, q)


def median_absolute_deviation(
    values: Sequence[float],
) -> float:
    """Compute the Median Absolute Deviation (MAD) of finite values.

    Parameters
    ----------
    values : Sequence[float]
        Sample sequence.

    Returns
    -------
    float
        Median absolute deviation.
    """
    data = _finite_values(values, name="MAD")
    center = median(data)
    return float(median(abs(value - center) for value in data))


def mad_outlier_indices(
    values: Sequence[float],
    *,
    threshold: float = 3.5,
) -> tuple[int, ...]:
    """Identify sample indices exceeding the MAD outlier threshold.

    Parameters
    ----------
    values : Sequence[float]
        Sample values to inspect.
    threshold : float, default=3.5
        Modified Z-score threshold for outlier classification.

    Returns
    -------
    tuple[int, ...]
        Indices of detected outliers.
    """
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or threshold <= 0
    ):
        raise ValueError("threshold must be finite and > 0")
    if not values:
        return ()

    data = _finite_values(values, name="MAD outlier detection")
    ordered = sorted(data)
    center = median(ordered)
    devs = sorted(abs(value - center) for value in data)
    mad = _percentile_presorted(devs, 0.5)
    if math.isclose(mad, 0.0, abs_tol=1e-15):
        return ()

    scale = 0.6744897501960817
    inv_denom = scale / mad
    return tuple(
        index
        for index, value in enumerate(data)
        if abs(value - center) * inv_denom > threshold
    )


def summarize(
    values: Iterable[float],
    *,
    percentiles: Sequence[float] = (0.25, 0.5, 0.75, 0.95),
    outlier_threshold: float = 3.5,
) -> SummaryStats:
    """Compute comprehensive descriptive summary statistics for sample values.

    Parameters
    ----------
    values : Iterable[float]
        Sample observations.
    percentiles : Sequence[float], default=(0.25, 0.5, 0.75, 0.95)
        Quantiles to compute.
    outlier_threshold : float, default=3.5
        MAD outlier threshold.

    Returns
    -------
    SummaryStats
        Calculated distribution metrics.
    """
    if (
        isinstance(outlier_threshold, bool)
        or not isinstance(outlier_threshold, (int, float))
        or not math.isfinite(outlier_threshold)
        or outlier_threshold <= 0
    ):
        raise ValueError("outlier_threshold must be finite and > 0")
    requested = tuple(float(q) for q in percentiles)
    if len(set(requested)) != len(requested):
        raise ValueError("percentiles must not contain duplicates")
    for q in requested:
        if not math.isfinite(q) or not 0.0 <= q <= 1.0:
            raise ValueError("percentile q must be finite and between 0 and 1")

    if _accel_fast_summary is not None and isinstance(values, (list, tuple)):
        try:
            raw_summary = _accel_fast_summary(
                values, requested, outlier_threshold
            )
            return SummaryStats(
                count=raw_summary["count"],
                minimum=raw_summary["minimum"],
                maximum=raw_summary["maximum"],
                mean=raw_summary["mean"],
                median=raw_summary["median"],
                variance=raw_summary["variance"],
                stdev=raw_summary["stdev"],
                coefficient_of_variation=raw_summary[
                    "coefficient_of_variation"
                ],
                mad=raw_summary["mad"],
                percentiles=raw_summary["percentiles"],
                outlier_indices=raw_summary["outlier_indices"],
            )
        except (TypeError, ValueError):
            raise

    data = _finite_values(values, name="samples")
    ordered = sorted(data)
    med = median(ordered)
    percentile_values = {q: _percentile_presorted(ordered, q) for q in requested}

    mean_value = fmean(data)
    variance_value = pvariance(data)
    stdev_value = pstdev(data)
    cv = (
        None
        if math.isclose(mean_value, 0.0, abs_tol=1e-15)
        else stdev_value / abs(mean_value)
    )

    devs = sorted(abs(x - med) for x in data)
    mad = _percentile_presorted(devs, 0.5)

    if (
        math.isclose(mad, 0.0, abs_tol=1e-15)
        or not math.isfinite(outlier_threshold)
        or outlier_threshold <= 0
    ):
        outliers: tuple[int, ...] = ()
    else:
        scale = 0.6744897501960817
        inv_denom = scale / mad
        outliers = tuple(
            index
            for index, value in enumerate(data)
            if abs(value - med) * inv_denom > outlier_threshold
        )

    return SummaryStats(
        count=len(data),
        minimum=min(data),
        maximum=max(data),
        mean=mean_value,
        median=med,
        variance=variance_value,
        stdev=stdev_value,
        coefficient_of_variation=cv,
        mad=mad,
        percentiles=percentile_values,
        outlier_indices=outliers,
    )


class RunningStats:
    """Constant-memory online summary statistics using Welford's algorithm.

    Maintains count, mean, min, max, total, and M2 (sum of squared deviations).
    Provides sample and population variance/stdev.
    Can be updated observation-by-observation in O(1) space, or merged in O(1) time
    using Chan's parallel variance formula.
    """

    __slots__ = ("_count", "_mean", "_m2", "_min", "_max", "_total")

    def __init__(self) -> None:
        self._count: int = 0
        self._mean: float = 0.0
        self._m2: float = 0.0
        self._min: float = float("inf")
        self._max: float = float("-inf")
        self._total: float = 0.0

    @classmethod
    def from_iterable(cls,
        values: Iterable[float],
    ) -> RunningStats:
        """Create an accumulator initialized from an iterable of samples."""
        stats = cls()
        stats.extend(values)
        return stats

    def update(self,
        value: float,
    ) -> None:
        """Add one sample value."""
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("value must be real numeric")
        val = float(value)
        if not math.isfinite(val):
            raise ValueError("value must be finite")

        self._count += 1
        delta = val - self._mean
        self._mean += delta / self._count
        delta2 = val - self._mean
        self._m2 += delta * delta2
        self._total += val
        if val < self._min:
            self._min = val
        if val > self._max:
            self._max = val

    def extend(self,
        values: Iterable[float],
    ) -> None:
        """Add multiple sample values."""
        if _accel_update_running_stats is not None and isinstance(
            values, (list, tuple)
        ):
            try:
                (
                    self._count,
                    self._mean,
                    self._m2,
                    self._min,
                    self._max,
                    self._total,
                ) = _accel_update_running_stats(
                    self._count,
                    self._mean,
                    self._m2,
                    self._min,
                    self._max,
                    self._total,
                    values,
                )
                return
            except (TypeError, ValueError):
                raise
        for value in values:
            self.update(value)

    def merge(self,
        other: RunningStats,
    ) -> RunningStats:
        """Merge this accumulator with another using parallel variance formula."""
        if not isinstance(other, RunningStats):
            raise TypeError("other must be RunningStats")
        if self._count == 0:
            return other.copy()
        if other._count == 0:
            return self.copy()

        combined = RunningStats()
        combined._count = self._count + other._count
        delta = other._mean - self._mean
        combined._mean = self._mean + delta * (other._count / combined._count)
        combined._m2 = (
            self._m2
            + other._m2
            + (delta * delta) * (self._count * other._count / combined._count)
        )
        combined._total = self._total + other._total
        combined._min = min(self._min, other._min)
        combined._max = max(self._max, other._max)
        return combined

    def copy(self) -> RunningStats:
        """Return a shallow copy of this accumulator."""
        clone = RunningStats()
        clone._count = self._count
        clone._mean = self._mean
        clone._m2 = self._m2
        clone._min = self._min
        clone._max = self._max
        clone._total = self._total
        return clone

    @property
    def count(self) -> int:
        return self._count

    @property
    def mean(self) -> float:
        return self._mean if self._count > 0 else 0.0

    @property
    def variance(self) -> float:
        """Sample variance s^2 (degrees of freedom = n - 1)."""
        return self._m2 / (self._count - 1) if self._count >= 2 else 0.0

    @property
    def pvariance(self) -> float:
        """Population variance sigma^2 (degrees of freedom = n)."""
        return self._m2 / self._count if self._count >= 1 else 0.0

    @property
    def stdev(self) -> float:
        """Sample standard deviation s."""
        return math.sqrt(self.variance)

    @property
    def pstdev(self) -> float:
        """Population standard deviation sigma."""
        return math.sqrt(self.pvariance)

    @property
    def minimum(self) -> float:
        return self._min if self._count > 0 else float("nan")

    @property
    def maximum(self) -> float:
        return self._max if self._count > 0 else float("nan")

    @property
    def total(self) -> float:
        return self._total

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean": self.mean,
            "variance": self.variance,
            "stdev": self.stdev,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "total": self.total,
        }

    def __repr__(self) -> str:
        return (
            f"RunningStats(count={self.count}, mean={self.mean:.6g}, "
            f"stdev={self.stdev:.6g}, min={self.minimum:.6g}, max={self.maximum:.6g})"
        )


@dataclass(frozen=True)
class ParetoObjective:
    """One objective direction for multi-objective Pareto analysis."""

    name: str
    lower_is_better: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("objective name must be nonempty string")
        if not isinstance(self.lower_is_better, bool):
            raise TypeError("lower_is_better must be bool")


def pareto_dominates(
    a: Sequence[float],
    b: Sequence[float],
    objectives: Sequence[ParetoObjective],
) -> bool:
    """Return whether point a Pareto-dominates point b.

    Point a dominates point b iff a is no worse than b across all objectives,
    and strictly better than b on at least one objective.
    """
    if len(a) != len(objectives) or len(b) != len(objectives):
        raise ValueError("point dimensions must match number of objectives")
    if not objectives:
        raise ValueError("at least one objective is required")

    no_worse = True
    strictly_better = False
    for val_a, val_b, obj in zip(a, b, objectives, strict=True):
        if not math.isfinite(val_a) or not math.isfinite(val_b):
            raise ValueError("objective values must be finite")
        if obj.lower_is_better:
            if val_a > val_b:
                no_worse = False
                break
            if val_a < val_b:
                strictly_better = True
        else:
            if val_a < val_b:
                no_worse = False
                break
            if val_a > val_b:
                strictly_better = True
    return no_worse and strictly_better


def pareto_frontier(
    items: Iterable[T],
    key: Callable[[T], Sequence[float]],
    objectives: Sequence[ParetoObjective],
) -> list[T]:
    """Compute the Pareto-optimal (non-dominated) subset of items.

    Uses an O(N log N) lexicographical sweep for 2D objectives, and
    sorted-frontier early pruning for higher dimensions.
    """
    item_list = list(items)
    if not item_list:
        return []
    obj_tuple = tuple(objectives)
    if not obj_tuple:
        raise ValueError("at least one objective is required")

    points = [tuple(float(v) for v in key(item)) for item in item_list]
    for pt in points:
        if len(pt) != len(obj_tuple):
            raise ValueError("key dimensions must match number of objectives")
        if not all(math.isfinite(v) for v in pt):
            raise ValueError("all objective values must be finite")

    num_dims = len(obj_tuple)
    #? Orient coordinates so lower is always better
    norm_points = [
        tuple(
            val if obj.lower_is_better else -val
            for val, obj in zip(pt, obj_tuple, strict=True)
        )
        for pt in points
    ]

    #? Special case 1D: all points matching global minimum are non-dominated
    if num_dims == 1:
        min_val = min(p[0] for p in norm_points)
        return [
            item
            for item, p in zip(item_list, norm_points, strict=True)
            if math.isclose(p[0], min_val, abs_tol=1e-15)
        ]

    #? Special case 2D: O(N log N) sorting + monotone sweep
    if num_dims == 2:
        sorted_indices = sorted(
            range(len(item_list)),
            key=lambda i: (norm_points[i][0], norm_points[i][1]),
        )
        frontier_indices: list[int] = []
        min_y = float("inf")
        idx = 0
        n_items = len(sorted_indices)
        while idx < n_items:
            curr_x = norm_points[sorted_indices[idx]][0]
            group: list[int] = []
            while idx < n_items and math.isclose(
                norm_points[sorted_indices[idx]][0], curr_x, abs_tol=1e-15
            ):
                group.append(sorted_indices[idx])
                idx += 1

            group_min_y = min(norm_points[i][1] for i in group)
            if group_min_y < min_y:
                for i in group:
                    if math.isclose(
                        norm_points[i][1], group_min_y, abs_tol=1e-15
                    ):
                        frontier_indices.append(i)
                min_y = group_min_y
        frontier_set = set(frontier_indices)
        return [item for i, item in enumerate(item_list) if i in frontier_set]

    #? General D >= 3: Sort by coordinates and prune against non-dominated set
    sorted_indices = sorted(range(len(item_list)), key=lambda i: norm_points[i])
    frontier_indices = []
    for cand_idx in sorted_indices:
        cand_pt = norm_points[cand_idx]
        is_dominated = False
        for f_idx in frontier_indices:
            f_pt = norm_points[f_idx]
            all_le = True
            strictly_less = False
            for d in range(num_dims):
                if f_pt[d] > cand_pt[d]:
                    all_le = False
                    break
                if f_pt[d] < cand_pt[d]:
                    strictly_less = True
            if all_le and strictly_less:
                is_dominated = True
                break
        if not is_dominated:
            frontier_indices.append(cand_idx)

    frontier_set = set(frontier_indices)
    return [item for i, item in enumerate(item_list) if i in frontier_set]


@dataclass(frozen=True)
class ECDFPoint:
    """One discrete step of an empirical cumulative distribution function."""

    value: float
    probability: float
    count: int


def ecdf(
    values: Iterable[float],
) -> list[ECDFPoint]:
    """Compute the exact empirical cumulative distribution function (ECDF).

    Accumulates exact rational masses to eliminate floating-point drift
    for tied values and guarantees the final probability equals 1.0.
    """
    data = _finite_values(values, name="values")
    n = len(data)
    counts = Counter(data)
    sorted_unique = sorted(counts.keys())

    cumulative_mass = Fraction(0, 1)
    points: list[ECDFPoint] = []
    for val in sorted_unique:
        cnt = counts[val]
        cumulative_mass += Fraction(cnt, n)
        points.append(
            ECDFPoint(
                value=val,
                probability=float(cumulative_mass),
                count=cnt,
            )
        )
    return points


__all__ = [
    "BootstrapMeanCI",
    "ECDFPoint",
    "NormalMeanSummary",
    "PairedEffect",
    "ParetoObjective",
    "RunningStats",
    "SummaryStats",
    "bootstrap_mean_ci",
    "ecdf",
    "mad_outlier_indices",
    "median_absolute_deviation",
    "normal_mean_summary",
    "paired_effect",
    "pareto_dominates",
    "pareto_frontier",
    "percentile",
    "summarize",
]

