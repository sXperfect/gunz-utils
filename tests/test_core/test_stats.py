"""Tests for dependency-free statistical helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.stats import (
    SummaryStats,
    bootstrap_mean_ci,
    mad_outlier_indices,
    median_absolute_deviation,
    normal_mean_summary,
    paired_effect,
    percentile,
    summarize,
)


def test_bootstrap_mean_ci_is_seeded_and_contains_observed_mean() -> None:
    first = bootstrap_mean_ci(
        [1.0, 2.0, 3.0, 4.0],
        samples=500,
        seed=7,
    )
    second = bootstrap_mean_ci(
        [1.0, 2.0, 3.0, 4.0],
        samples=500,
        seed=7,
    )

    assert first == second
    assert first.low <= first.mean <= first.high
    assert first.observations == 4


def test_bootstrap_mean_ci_validates_inputs() -> None:
    with pytest.raises(ValueError, match="empty"):
        bootstrap_mean_ci([])

    with pytest.raises(ValueError, match="finite"):
        bootstrap_mean_ci([1.0, math.inf])

    with pytest.raises(ValueError, match="confidence"):
        bootstrap_mean_ci([1.0], confidence=1.0)

    with pytest.raises(ValueError, match="samples"):
        bootstrap_mean_ci([1.0], samples=0)


def test_paired_effect_matches_known_differences() -> None:
    result = paired_effect(
        [2.0, 4.0, 7.0],
        [1.0, 2.0, 4.0],
    )

    #? Pairwise differences are [1, 2, 3].
    assert math.isclose(result.mean_difference, 2.0)
    assert math.isclose(result.standard_deviation, 1.0)
    assert math.isclose(result.standardized_effect, 2.0)
    assert result.observations == 3


def test_paired_effect_zero_variance_has_no_standardized_effect() -> None:
    result = paired_effect(
        [2.0, 3.0],
        [1.0, 2.0],
    )

    assert math.isclose(result.mean_difference, 1.0)
    assert math.isclose(result.standard_deviation, 0.0, abs_tol=1e-15)
    assert result.standardized_effect is None


def test_paired_effect_validates_pairing_and_finiteness() -> None:
    with pytest.raises(ValueError, match="equal length"):
        paired_effect(
            [1.0, 2.0],
            [1.0],
        )

    with pytest.raises(ValueError, match="finite"):
        paired_effect(
            [1.0, math.nan],
            [1.0, 2.0],
        )


def test_paired_effect_single_observation_is_undefined() -> None:
    result = paired_effect(
        [2.0],
        [1.0],
    )

    assert math.isclose(result.standard_deviation, 0.0, abs_tol=1e-15)
    assert result.standardized_effect is None



def test_normal_mean_summary_matches_known_replicates() -> None:
    result = normal_mean_summary(
        [1.0, 2.0, 3.0],
        confidence_z=1.0,
    )

    assert result.observations == 3
    assert math.isclose(result.mean, 2.0)
    assert math.isclose(result.standard_deviation, 1.0)
    assert math.isclose(result.low, 2.0 - 1.0 / math.sqrt(3.0))
    assert math.isclose(result.high, 2.0 + 1.0 / math.sqrt(3.0))


def test_normal_mean_summary_single_observation_collapses_interval() -> None:
    result = normal_mean_summary(
        [4.0],
    )

    assert math.isclose(result.mean, 4.0)
    assert math.isclose(result.standard_deviation, 0.0, abs_tol=1e-15)
    assert math.isclose(result.low, 4.0)
    assert math.isclose(result.high, 4.0)


def test_normal_mean_summary_validates_z_value() -> None:
    with pytest.raises(ValueError, match="confidence_z"):
        normal_mean_summary(
            [1.0, 2.0],
            confidence_z=math.inf,
        )


def test_paired_effect_handles_extreme_finite_values_stably() -> None:
    result = paired_effect(
        [1e308, -1e308],
        [0.0, 0.0],
    )

    assert math.isfinite(result.standard_deviation)
    assert result.standard_deviation > 1e308
    assert result.standardized_effect is not None
    assert math.isclose(result.standardized_effect, 0.0, abs_tol=1e-15)


def test_paired_effect_rejects_overflowing_pairwise_difference() -> None:
    with pytest.raises(ValueError, match="paired differences"):
        paired_effect(
            [1e308],
            [-1e308],
        )


def test_normal_mean_summary_handles_extreme_finite_values_stably() -> None:
    result = normal_mean_summary(
        [1e308, -1e308],
        confidence_z=1.0,
    )

    assert math.isfinite(result.standard_deviation)
    assert math.isfinite(result.low)
    assert math.isfinite(result.high)
    assert math.isclose(result.low, -1e308)
    assert math.isclose(result.high, 1e308)


def test_normal_mean_summary_rejects_unrepresentable_interval() -> None:
    with pytest.raises(OverflowError, match="interval"):
        normal_mean_summary(
            [1e308, -1e308],
            confidence_z=1.96,
        )


def test_statistics_reject_boolean_and_non_numeric_domains() -> None:
    with pytest.raises(ValueError, match="real numeric"):
        paired_effect([True], [0.0])
    with pytest.raises(ValueError, match="samples"):
        bootstrap_mean_ci([1.0], samples=True)
    with pytest.raises(ValueError, match="seed"):
        bootstrap_mean_ci([1.0], seed=True)
    with pytest.raises(ValueError, match="confidence_z"):
        normal_mean_summary([1.0, 2.0], confidence_z=True)


def test_percentile_computation_and_bounds() -> None:
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert math.isclose(percentile(data, 0.0), 1.0)
    assert math.isclose(percentile(data, 0.5), 3.0)
    assert math.isclose(percentile(data, 1.0), 5.0)
    assert math.isclose(percentile(data, 0.25), 2.0)
    assert math.isclose(percentile([42.0], 0.5), 42.0)

    for invalid_q in (-0.1, 1.1, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="percentile q"):
            percentile(data, invalid_q)


def test_median_absolute_deviation() -> None:
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    #? Center is 5.0, absolute deviations: 4, 3, 2, 1, 0, 1, 2, 3, 4 -> median is 2.0
    assert math.isclose(median_absolute_deviation(data), 2.0)

    identical = [3.0, 3.0, 3.0]
    assert math.isclose(median_absolute_deviation(identical), 0.0)


def test_mad_outlier_indices() -> None:
    data = [10.0, 10.1, 10.2, 9.9, 10.0, 100.0]
    outliers = mad_outlier_indices(data, threshold=3.5)
    assert outliers == (5,)

    assert mad_outlier_indices([]) == ()
    assert mad_outlier_indices([5.0, 5.0, 5.0]) == ()

    for invalid_thresh in (-1.0, 0.0, float("nan"), True):
        with pytest.raises(ValueError, match="threshold"):
            mad_outlier_indices(data, threshold=invalid_thresh)


def test_summarize_sample_metrics() -> None:
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]
    result = summarize(data, percentiles=(0.25, 0.5, 0.75))

    assert isinstance(result, SummaryStats)
    assert result.count == 6
    assert math.isclose(result.minimum, 1.0)
    assert math.isclose(result.maximum, 100.0)
    assert result.outlier_indices == (5,)
    assert 0.25 in result.percentiles
    assert 0.5 in result.percentiles

    with pytest.raises(ValueError, match="samples must not be empty"):
        summarize([])

    with pytest.raises(ValueError, match="duplicates"):
        summarize(data, percentiles=(0.5, 0.5))

    with pytest.raises(ValueError, match="finite"):
        summarize([1.0, math.nan])


def test_bootstrap_mean_ci_adversarial_domain_invariants() -> None:
    #? Boolean rejection across all parameters
    with pytest.raises(ValueError, match="confidence"):
        bootstrap_mean_ci([1.0, 2.0], confidence=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="samples"):
        bootstrap_mean_ci([1.0, 2.0], samples=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="seed"):
        bootstrap_mean_ci([1.0, 2.0], seed=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="real numeric"):
        bootstrap_mean_ci([1.0, True, 2.0])  # type: ignore[list-item]

    with pytest.raises(ValueError, match="real numeric"):
        bootstrap_mean_ci(["not_a_number"])  # type: ignore[list-item]

    #? Boundary and non-finite confidence
    for conf in (0.0, 1.0, -0.5, 1.5, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="confidence"):
            bootstrap_mean_ci([1.0, 2.0], confidence=conf)

    #? Samples count bounds
    for s in (0, -1, -100):
        with pytest.raises(ValueError, match="samples"):
            bootstrap_mean_ci([1.0, 2.0], samples=s)

    #? Seed type checking
    with pytest.raises(ValueError, match="seed"):
        bootstrap_mean_ci([1.0, 2.0], seed="invalid")  # type: ignore[arg-type]

    #? Single observation bootstrap
    single = bootstrap_mean_ci([42.0], samples=100, seed=1)
    assert math.isclose(single.mean, 42.0)
    assert math.isclose(single.low, 42.0)
    assert math.isclose(single.high, 42.0)
    assert single.observations == 1


def test_paired_effect_adversarial_domain_invariants() -> None:
    #? Boolean rejection
    with pytest.raises(ValueError, match="real numeric"):
        paired_effect([True, 1.0], [0.0, 1.0])  # type: ignore[list-item]

    with pytest.raises(ValueError, match="real numeric"):
        paired_effect([0.0, 1.0], [False, 1.0])  # type: ignore[list-item]

    #? Non-numeric objects
    with pytest.raises(ValueError, match="real numeric"):
        paired_effect(["a", "b"], [1.0, 2.0])  # type: ignore[list-item]

    #? Empty sequences
    with pytest.raises(ValueError, match="empty"):
        paired_effect([], [])

    #? Non-finite in left or right
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            paired_effect([bad, 1.0], [0.0, 1.0])
        with pytest.raises(ValueError, match="finite"):
            paired_effect([0.0, 1.0], [bad, 1.0])

    #? Identical samples: zero difference, zero sd, standardized_effect is None
    res = paired_effect([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert math.isclose(res.mean_difference, 0.0, abs_tol=1e-15)
    assert math.isclose(res.standard_deviation, 0.0, abs_tol=1e-15)
    assert res.standardized_effect is None
    assert res.observations == 3


def test_normal_mean_summary_adversarial_domain_invariants() -> None:
    #? Boolean rejection
    with pytest.raises(ValueError, match="confidence_z"):
        normal_mean_summary([1.0, 2.0], confidence_z=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="real numeric"):
        normal_mean_summary([True, 2.0])  # type: ignore[list-item]

    #? Negative and non-finite confidence_z
    for z in (-0.01, -1.0, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="confidence_z"):
            normal_mean_summary([1.0, 2.0], confidence_z=z)

    #? Empty observations
    with pytest.raises(ValueError, match="empty"):
        normal_mean_summary([])

    #? Non-numeric observations
    with pytest.raises(ValueError, match="real numeric"):
        normal_mean_summary(["foo", "bar"])  # type: ignore[list-item]

    #? Single observation collapses margin to zero
    res = normal_mean_summary([10.5], confidence_z=2.5)
    assert res.observations == 1
    assert math.isclose(res.mean, 10.5)
    assert math.isclose(res.standard_deviation, 0.0, abs_tol=1e-15)
    assert math.isclose(res.low, 10.5)
    assert math.isclose(res.high, 10.5)
    assert math.isclose(res.confidence_z, 2.5)


