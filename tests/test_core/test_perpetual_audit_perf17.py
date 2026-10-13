"""Phase 17 perpetual audit: round-3 re-audit of async_utils/retry/rate_limit/
time_utils.

Focused on the deepest corner a prior pass could miss: ``with_timeout`` with a
zero timeout spuriously cancels an awaitable that is immediately satisfiable
but yields one event-loop tick.

This test is expected to be RED against base ``23d70e7`` and documents the
correct behavior after a fix.
"""

from __future__ import annotations

import asyncio

import pytest

from gunz_utils.async_utils import with_timeout


# ---------------------------------------------------------------------------
# async_utils.with_timeout: a zero timeout must mean "do not wait" and must
# still let an awaitable that is immediately satisfiable complete.
#
# The codebase's established convention for ``timeout=0`` is "do not wait,
# succeed if the work is already ready" (see the phase-14 AsyncBulkhead fix,
# which gives ``asyncio.wait_for(coro, 0)`` a single event-loop tick because it
# "never lets a ready coroutine complete"; AsyncRateLimiter.acquire(timeout=0)
# and retry's zero-timeout semantics follow the same rule).
#
# ``with_timeout`` uses ``asyncio.timeout(0)`` which has the same defect: an
# awaitable that is ready (no real delay) but awaits once (e.g.
# ``await asyncio.sleep(0)``) is cancelled and raises TimeoutError, even though
# no waiting was required. An awaitable that returns without yielding completes
# fine, so the behavior is inconsistent based purely on whether the coroutine
# schedules one tick.
# ---------------------------------------------------------------------------
def test_with_timeout_zero_allows_immediately_satisfiable_awaitable() -> None:
    async def ready_work() -> str:
        await asyncio.sleep(0)  # one tick, no real delay
        return "ok"

    # A zero timeout means "don't wait": work that needs no real time must
    # complete, not be spuriously cancelled.
    assert asyncio.run(with_timeout(ready_work(), 0)) == "ok"


def test_with_timeout_zero_still_rejects_work_needing_time() -> None:
    async def slow_work() -> str:
        await asyncio.sleep(1.0)
        return "ok"

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(with_timeout(slow_work(), 0))


# ---------------------------------------------------------------------------
# [REGESSION TEST - implementer addition, flagged for auditor review]
# Busy-spin bound: a pathological never-completing zero-delay coroutine
# (``while True: await asyncio.sleep(0)``) must fail fast under
# ``with_timeout(..., 0)`` rather than draining zero-delay ticks forever at
# 100% CPU. The drain is bounded, so this raises TimeoutError instead of
# hanging. (This test would hang indefinitely on the unbounded drain.)
# ---------------------------------------------------------------------------
def test_with_timeout_zero_busy_spin_is_bounded() -> None:
    async def runaway() -> str:
        while True:
            await asyncio.sleep(0)

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(with_timeout(runaway(), 0))
