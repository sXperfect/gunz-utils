"""Phase 20 perpetual audit: round-3 re-audit of hashing/parsing/limits/signals.

Focused on the deepest DEFERRED corners two prior passes missed: non-representable
numeric inputs must surface as documented ``ValueError`` (validators) or a
fallback default (parsers), never an internal ``OverflowError`` leak.

Both findings are the same defect class as the phase-19 cache TTL validator
(unguarded ``float()`` of a huge integer leaks ``OverflowError``) but in
modules the prior passes did not harden: ``parsing.safe_float`` and
``limits.Limits`` / ``ResourceBudget``.

These tests are expected to be RED against base ``f0b3e98`` and document the
correct behavior after a fix.
"""

from __future__ import annotations

import pytest

from gunz_utils.limits import Limits, ResourceBudget
from gunz_utils.parsing import safe_float


# ---------------------------------------------------------------------------
# parsing.safe_float leaks OverflowError for a huge-integer input.
#
# ``safe_float`` (parsing.py:128-131) converts via ``float(stripped)`` and only
# catches ``(ValueError, TypeError)``. Unlike ``safe_int`` (which catches
# ``OverflowError``), a large integer that is finite as an int but not
# float-representable (e.g. ``10**400``) raises ``float(...)``'s
# ``OverflowError: int too large to convert to float`` instead of returning the
# fallback default. The documented contract is "return a fallback when parsing
# or bounds fail", so a non-representable numeric input is a parse failure and
# must not crash with an internal OverflowError.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_safe_float_huge_int_returns_default_not_overflow(value: int) -> None:
    assert safe_float(value) is None
    assert safe_float(value, default=-1.0) == -1.0


# ---------------------------------------------------------------------------
# limits.Limits.__post_init__ leaks OverflowError for a huge-integer timeout.
#
# ``Limits.__post_init__`` (limits.py:39-45) evaluates
# ``math.isfinite(float(self.timeout))`` without guarding the ``float()``
# conversion, so ``Limits(timeout=10**400)`` leaks ``OverflowError`` instead of
# the documented ``ValueError`` ("timeout must be a finite non-negative number
# or None"). ``ResourceBudget`` constructs a ``Limits`` internally (limits.py:124),
# so ``ResourceBudget(timeout=10**400)`` leaks the same way. This is the same
# unguarded-``float()`` defect class as the phase-19 cache TTL validator.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_limits_timeout_huge_int_raises_valueerror_not_overflow(value: int) -> None:
    with pytest.raises(ValueError, match="timeout"):
        Limits(timeout=value)
    with pytest.raises(ValueError, match="timeout"):
        ResourceBudget(timeout=value)
