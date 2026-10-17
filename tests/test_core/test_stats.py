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
    assert result.mean_difference == pytest.approx(2.0)
    assert result.standard_deviation == pytest.approx(1.0)
    assert result.standardized_effect == pytest.approx(2.0)
    assert result.observations == 3


def test_paired_effect_zero_variance_has_no_standardized_effect() -> None:
    result = paired_effect(
        [2.0, 3.0],
        [1.0, 2.0],
    )

    assert result.mean_difference == pytest.approx(1.0)
    assert result.standard_deviation == pytest.approx(0.0)
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

    assert result.standard_deviation == pytest.approx(0.0)
    assert result.standardized_effect is None



def test_normal_mean_summary_matches_known_replicates() -> None:
    result = normal_mean_summary(
        [1.0, 2.0, 3.0],
        confidence_z=1.0,
    )

    assert result.observations == 3
    assert result.mean == pytest.approx(2.0)
    assert result.standard_deviation == pytest.approx(1.0)
    assert result.low == pytest.approx(
        2.0 - 1.0 / math.sqrt(3.0)
    )
    assert result.high == pytest.approx(
        2.0 + 1.0 / math.sqrt(3.0)
    )


def test_normal_mean_summary_single_observation_collapses_interval() -> None:
    result = normal_mean_summary(
        [4.0],
    )

    assert result.mean == pytest.approx(4.0)
    assert result.standard_deviation == pytest.approx(0.0)
    assert result.low == pytest.approx(4.0)
    assert result.high == pytest.approx(4.0)


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
    assert result.standardized_effect == pytest.approx(0.0)


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
    assert result.low == pytest.approx(-1e308)
    assert result.high == pytest.approx(1e308)


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

