"""Perpetual correctness & performance audit regressions (phase 14).

Each test pins a defect found during the round-2 re-audit of ``enums``,
``deprecation``, ``context``, ``resilience``, ``faults``, and ``plugins``.
The tests currently FAIL against the audited revision (87dd2f3, which
includes the phase-1..13 fixes); they encode the expected post-fix behavior
and should pass once the implementation is corrected. Production code is
intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.enums import BaseStrEnum
from gunz_utils.resilience import AsyncBulkhead

# ---------------------------------------------------------------------------
# resilience.AsyncBulkhead.run: ``timeout=0`` raises TimeoutError even when a
# permit is immediately available.
#
# ``run`` (resilience.py) acquires the permit with
# ``asyncio.wait_for(self._semaphore.acquire(), timeout)`` when a timeout is
# given. ``asyncio.wait_for`` with timeout=0 never lets a ready coroutine
# complete -- it returns as soon as the zero-second budget elapses, so even a
# bulkhead with free permits reports ``TimeoutError: bulkhead acquisition
# timed out``. A zero timeout should mean "do not wait": acquire immediately
# when a permit is free, and only fail if none is available right now.
# Verified: AsyncBulkhead(2).run(op, timeout=0) raises TimeoutError although
# both permits are free, while timeout=0.0001/None succeed.
# ---------------------------------------------------------------------------


def test_bulkhead_timeout_zero_acquires_available_permit() -> None:
    async def operation() -> str:
        return "ran"

    async def scenario() -> None:
        bulkhead = AsyncBulkhead(2)
        result = await bulkhead.run(operation, timeout=0)
        assert result == "ran"

    asyncio.run(scenario())


def test_bulkhead_timeout_zero_fails_only_when_no_permit() -> None:
    async def operation() -> str:
        return "ran"

    async def scenario() -> None:
        bulkhead = AsyncBulkhead(1)
        assert bulkhead.available == 1
        result = await bulkhead.run(operation, timeout=0)
        assert result == "ran"

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# enums.BaseStrEnum.from_fuzzy_string: a member's NAME can shadow another
# member's VALUE, so passing a value returns the wrong member.
#
# ``_get_fuzzy_map`` (enums.py) adds, per member and only if not already
# present: the normalized value, the raw lowercase value, and the lowercase
# name. When one member's name normalizes to another member's value, the
# earlier member's name occupies the key first, so the later member's value
# is never registered and a value lookup resolves to the wrong member.
# Example: class E(BaseStrEnum): FOO = "bar"; BAR = "foo". The value "foo"
# belongs to BAR, but from_fuzzy_string("foo") returns FOO because FOO's name
# ("foo") was registered first. Expected: a member's value must take
# precedence over another member's name so passing a value returns the member
# that owns it.
# ---------------------------------------------------------------------------


def test_str_enum_value_lookup_not_shadowed_by_name() -> None:
    class E(BaseStrEnum):
        FOO = "bar"
        BAR = "foo"

    assert E.from_fuzzy_string("foo") is E.BAR, (
        'from_fuzzy_string("foo") should return BAR (whose value is "foo"), '
        "not FOO (shadowed by FOO's name)"
    )


def test_str_enum_value_lookup_returns_owning_member_by_name() -> None:
    class E(BaseStrEnum):
        FOO = "bar"
        BAR = "foo"

    assert E.from_fuzzy_string("BAR") is E.BAR
    assert E.from_fuzzy_string("FOO") is E.FOO
