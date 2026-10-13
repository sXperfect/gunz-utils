"""Perpetual correctness & performance audit regressions (phase 12).

Each test pins a defect found during the round-2 re-audit of
``async_utils`` (and related modules). The tests currently FAIL against the
audited revision (463572b, which includes the phase-6..11 fixes); they encode
the expected post-fix behavior and should pass once the implementation is
corrected. Production code is intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Iterator

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.async_utils import with_timeout

# ---------------------------------------------------------------------------
# async_utils.with_timeout: an integer timeout that is too large to convert
# to float leaks ``OverflowError`` instead of the documented ``ValueError``.
#
# ``with_timeout`` (async_utils.py) rejects invalid timeouts with
# "timeout must be a finite non-negative number or None". Its validation
# evaluates ``math.isfinite(float(timeout))`` without guarding the ``float()``
# conversion, so an integer such as ``10**400`` (finite as an int, but not
# float-representable) raises ``OverflowError: int too large to convert to
# float``. The sibling helper ``time_utils.monotonic_deadline``
# (time_utils.py) already guards this exact case with a ``try/except
# OverflowError`` that maps it to ``ValueError``. ``with_timeout`` should be
# consistent: an out-of-range timeout must raise ``ValueError``, never leak an
# internal ``OverflowError``.
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _raises_value_error() -> Iterator[None]:
    try:
        yield
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_with_timeout_huge_integer_raises_valueerror_not_overflow() -> None:
    async def operation() -> int:
        return 1

    with _raises_value_error():
        asyncio.run(with_timeout(operation(), 10**400))
