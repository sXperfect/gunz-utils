"""Phase 19 perpetual audit: round-3 re-audit of cache/collections/iteration/buffers.

Focused on the deepest corner a prior pass could miss: the cache TTL validator
leaks ``OverflowError`` for an integer TTL too large to convert to float,
instead of the documented ``ValueError``.

These tests are expected to be RED against base ``450d8fa`` and document the
correct behavior after a fix.
"""

from __future__ import annotations

import pytest

from gunz_utils.cache import async_ttl_cache, ttl_cache


# ---------------------------------------------------------------------------
# cache._validate_cache_bounds leaks OverflowError for a huge-integer ttl.
#
# ``_validate_cache_bounds`` (cache.py:76-82) evaluates
# ``math.isfinite(float(ttl))`` without guarding the ``float()`` conversion.
# An integer such as ``10**400`` is finite as an int but not float-representable,
# so ``float(10**400)`` raises ``OverflowError: int too large to convert to
# float`` instead of the documented ``ValueError`` ("ttl must be a finite
# non-negative number"). This is the same defect class as the phase-12
# ``with_timeout`` / ``time_utils.monotonic_deadline`` fix, but it was not
# applied here.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("factory", [ttl_cache, async_ttl_cache])
def test_cache_rejects_unrepresentable_ttl_as_valueerror_not_overflow(
    factory: object,
) -> None:
    with pytest.raises(ValueError, match="ttl"):
        factory(ttl=10**400)  # type: ignore[operator]

    # A valid finite ttl is still accepted.
    factory(ttl=1.0)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# [REGRESSION TEST - implementer addition, flagged for auditor review]
# Validation-ordering regression: after closing the OverflowError leak for a
# huge-int ttl, non-numeric ttls (None / str) must STILL raise the documented
# ValueError (not TypeError or a raw float-conversion ValueError). The type
# guard must run before the float() conversion.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("factory", [ttl_cache, async_ttl_cache])
@pytest.mark.parametrize("bad_ttl", [None, "abc"])
def test_cache_rejects_non_numeric_ttl_with_documented_valueerror(
    factory: object,
    bad_ttl: object,
) -> None:
    with pytest.raises(ValueError, match="ttl"):
        factory(ttl=bad_ttl)  # type: ignore[operator]
