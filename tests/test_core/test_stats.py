"""Tests for dependency-free statistical helpers."""

from __future__ import annotations

import math

import pytest

from gunz_utils.stats import (
    bootstrap_mean_ci,
    normal_mean_summary,
    paired_effect,
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

    # Pairwise differences are [1, 2, 3].
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
