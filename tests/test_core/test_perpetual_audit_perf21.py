"""Phase 21 perpetual audit: round-3 re-audit of testing/testkit/binary/stats.

Focused on the deepest DEFERRED corner a prior pass could miss: stats.py leaks
``OverflowError`` from unguarded ``float()`` conversions when given a finite
``Real`` that is not float-representable (e.g. the integer ``10**400``). This
is the same defect class as the phase-19 cache TTL / phase-20 parsing-limits
fixes, but stats.py was not hardened there.

The three conversion sites are ``_finite_values`` (stats.py:66),
``bootstrap_mean_ci`` confidence validation (stats.py:139-140), and
``normal_mean_summary`` confidence_z validation (stats.py:336). All three must
surface the documented ``ValueError`` instead of an internal ``OverflowError``.

These tests are expected to be RED against base ``e2c541a`` and document the
correct behavior after a fix.
"""

from __future__ import annotations

import pytest

from gunz_utils.stats import (
    bootstrap_mean_ci,
    normal_mean_summary,
    paired_effect,
)


# ---------------------------------------------------------------------------
# stats._finite_values leaks OverflowError for a non-float-representable finite
# Real observation.
#
# ``_finite_values`` (stats.py:66) runs ``float(value)`` on each observation
# without guarding the conversion. A ``Real`` that is finite as an int but not
# float-representable (e.g. ``10**400``) raises
# ``OverflowError: int too large to convert to float`` instead of the
# documented ``ValueError`` ("values must contain only finite values"). Every
# entry point routes observations through ``_finite_values``: ``bootstrap_mean_ci``,
# ``normal_mean_summary``, and ``paired_effect``.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "call",
    [
        lambda: bootstrap_mean_ci([10**400]),
        lambda: bootstrap_mean_ci([-(10**400)]),
        lambda: normal_mean_summary([10**400]),
        lambda: paired_effect([10**400], [1.0]),
        lambda: paired_effect([1.0], [10**400]),
    ],
)
def test_stats_observation_huge_int_raises_valueerror_not_overflow(
    call: object,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        call()  # type: ignore[operator]


# ---------------------------------------------------------------------------
# stats.bootstrap_mean_ci leaks OverflowError from the confidence validator.
#
# The confidence check (stats.py:139-140) calls ``float(confidence)``
# unguarded in ``math.isfinite`` and the range comparison. A huge-int
# ``confidence=10**400`` leaks ``OverflowError`` instead of the documented
# ``ValueError`` ("confidence must be a finite number strictly between 0 and 1").
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("confidence", [10**400, -(10**400)])
def test_bootstrap_confidence_huge_int_raises_valueerror_not_overflow(
    confidence: int,
) -> None:
    with pytest.raises(ValueError, match="confidence"):
        bootstrap_mean_ci([1.0, 2.0], confidence=confidence)


# ---------------------------------------------------------------------------
# stats.normal_mean_summary leaks OverflowError from the confidence_z validator.
#
# The confidence_z check (stats.py:336) calls ``float(confidence_z)``
# unguarded. A huge-int ``confidence_z=10**400`` leaks ``OverflowError``
# instead of the documented ``ValueError`` ("confidence_z must be a
# non-negative finite number").
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("confidence_z", [10**400, -(10**400)])
def test_normal_confidence_z_huge_int_raises_valueerror_not_overflow(
    confidence_z: int,
) -> None:
    with pytest.raises(ValueError, match="confidence_z"):
        normal_mean_summary([1.0, 2.0], confidence_z=confidence_z)
