"""Small dependency-free statistical helpers for repeated experiments."""

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass
from numbers import Real
from statistics import fmean, stdev


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


def _finite_values(
    values: Iterable[float],
    *,
    name: str,
) -> list[float]:
    """Convert values to finite floats and require at least one observation."""
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
    account for dependence between observations.
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


__all__ = [
    "BootstrapMeanCI",
    "NormalMeanSummary",
    "PairedEffect",
    "bootstrap_mean_ci",
    "normal_mean_summary",
    "paired_effect",
]


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
