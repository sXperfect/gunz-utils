"""Perpetual correctness & performance audit regressions (phase 4).

Each test pins a defect found during the round-4 audit of
``gunz_utils.{collections,stats,time_utils,timing,versioning}``. The tests
currently FAIL against the audited revision (2c31727, which includes the
phase-1..3 fixes); they encode the expected post-fix behavior and should be
un-skipped once the implementation is corrected. Production code is
intentionally left untouched.
"""

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
    bootstrap_mean_ci,
    normal_mean_summary,
    paired_effect,
)
from gunz_utils.time_utils import expired, monotonic_deadline, remaining

# ---------------------------------------------------------------------------
# time_utils: a huge integer timeout/deadline leaks an uncaught OverflowError
# from ``float(int)`` instead of the documented ValueError.
#
# ``monotonic_deadline`` / ``remaining`` / ``expired`` document that a
# non-finite or non-numeric timeout/deadline raises ``ValueError``, and they
# validate ``math.isfinite(float(timeout))``. But converting an integer too
# large for a float (e.g. ``10**400``) raises ``OverflowError: int too large
# to convert to float`` *inside* that validation expression, and it is not
# caught. Expected behavior: treat such a value as invalid and raise
# ``ValueError`` (matching the documented contract), not leak the internal
# ``OverflowError``.
# ---------------------------------------------------------------------------


def test_monotonic_deadline_rejects_huge_int_timeout() -> None:
    with pytest.raises(ValueError):
        monotonic_deadline(10**400)


def test_remaining_rejects_huge_int_deadline() -> None:
    with pytest.raises(ValueError):
        remaining(10**400)


def test_expired_rejects_huge_int_deadline() -> None:
    with pytest.raises(ValueError):
        expired(10**400)


# ---------------------------------------------------------------------------
# stats: finite observations whose intermediate sum overflows raise an
# undocumented raw ``OverflowError: intermediate overflow in fsum`` from
# ``statistics.fmean`` even though the arithmetic mean is representable.
#
# For ``paired_effect([1e308, 1e308], [0.0, 0.0])`` the mean (1e308) is
# finite, but ``statistics.fsum`` overflows on the intermediate sum (2e308)
# before dividing, so the function raises instead of returning the result.
# ``normal_mean_summary``/``bootstrap_mean_ci`` leak the same raw fsum error
# for ``[1e308] * n`` inputs, bypassing the documented, controlled
# ``OverflowError`` they otherwise raise for unrepresentable intervals. All
# three should return the representable finite result (or a documented,
# controlled error), not an undocumented internal fsum ``OverflowError``.
# ---------------------------------------------------------------------------


def test_paired_effect_returns_representable_mean_despite_sum_overflow() -> None:
    result = paired_effect([1e308, 1e308], [0.0, 0.0])
    assert result.mean_difference == 1e308
    assert math.isfinite(result.mean_difference)
    assert result.standard_deviation == 0.0
    assert result.standardized_effect is None


def test_normal_mean_summary_returns_representable_mean_despite_sum_overflow() -> None:
    result = normal_mean_summary([1e308, 1e308], confidence_z=1.0)
    assert result.mean == 1e308
    assert math.isfinite(result.mean)
    assert math.isfinite(result.low)
    assert math.isfinite(result.high)


def test_bootstrap_mean_ci_returns_finite_interval_despite_sum_overflow() -> None:
    result = bootstrap_mean_ci([1e308] * 50, samples=10)
    assert result.mean == 1e308
    assert math.isfinite(result.mean)
    assert math.isfinite(result.low)
    assert math.isfinite(result.high)
