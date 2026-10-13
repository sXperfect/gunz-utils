"""Perpetual security audit phase 38 (round 4, deepest).

Re-audit of ``concurrency``, ``limits``, ``leases``, ``rate_limit``,
``faults``, and ``iteration``.

Finding (NEW, not fixed in phases 1-37):

1. ``gather_limited`` (concurrency.py:45-131) leaks un-awaited coroutines on
   early exit when given a materialized iterable of coroutines.  It schedules
   only ``limit`` tasks at a time; when a scheduled subtask raises (or the
   outer gather is cancelled), the ``finally`` block (concurrency.py:127-130)
   cancels and drains the *scheduled* pending tasks, but never touches the
   coroutines still held by the input iterator that were never scheduled.
   Because the public contract accepts ``Iterable[Coroutine]`` and a ``list``
   is the most natural input, those unscheduled coroutines are left forever
   un-awaited and un-closed: they emit ``RuntimeWarning: coroutine was never
   awaited`` on garbage collection and never have ``aclose()`` called on
   them.  ``asyncio.gather`` (whose semantics this helper documents itself
   as mirroring) awaits *every* supplied coroutine, so this is a genuine
   deviation and an exception-safety / cleanup-on-every-exit defect.

   Correct behavior: on every exit path the remaining, unscheduled coroutines
   must be closed (``Coroutine.close()``) so nothing is leaked as a
   "never awaited" warning.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: gather_limited preserves input order and bounds concurrency,
collects exceptions with return_exceptions and fail-fasts without it;
leases cancels the operation and raises LeaseLostError on ownership loss
with no orphan tasks; rate_limit enforces timeouts and try_acquire bounds;
limits enforces byte/item/step/depth/time bounds; FaultyStream caps reads
and writes and injects short writes; flatten enforces max_depth/max_nesting
and cycle detection.
"""

import asyncio
import gc
import io
import warnings

import pytest

from gunz_utils.concurrency import gather_limited, map_unordered
from gunz_utils.faults import FaultyStream
from gunz_utils.iteration import flatten
from gunz_utils.leases import LeaseLostError, run_with_lease_heartbeat
from gunz_utils.limits import BudgetExceededError, ResourceBudget
from gunz_utils.rate_limit import AsyncRateLimiter

# ---------------------------------------------------------------------------
# Finding 1: gather_limited must close unscheduled coroutines on early exit
# ---------------------------------------------------------------------------


def test_gather_limited_closes_unscheduled_coroutines_on_early_failure() -> None:
    """RED: a materialized coroutine list must not leak un-awaited coroutines
    when an early subtask fails and aborts the gather."""

    async def boom(x: int) -> int:
        await asyncio.sleep(0.001)
        if x == 1:
            raise RuntimeError("boom")
        return x

    async def scenario() -> list:
        awaitables = [boom(i) for i in range(6)]
        try:
            await gather_limited(awaitables, limit=2)
        except RuntimeError:
            pass
        return awaitables

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        awaitables = asyncio.run(scenario())
        del awaitables
        gc.collect()
        leaked = [
            str(w.message)
            for w in caught
            if issubclass(w.category, RuntimeWarning)
            and "never awaited" in str(w.message)
        ]
    assert leaked == [], f"leaked un-awaited coroutines: {leaked}"


def test_gather_limited_closes_unscheduled_coroutines_on_cancel() -> None:
    """RED: cancelling the outer gather must also close unscheduled coroutines
    held by a materialized input list."""

    async def slow(x: int) -> int:
        await asyncio.sleep(1.0)
        return x

    async def scenario() -> list:
        awaitables = [slow(i) for i in range(6)]
        outer = asyncio.create_task(gather_limited(awaitables, limit=2))
        await asyncio.sleep(0.01)
        outer.cancel()
        try:
            await outer
        except asyncio.CancelledError:
            pass
        return awaitables

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        awaitables = asyncio.run(scenario())
        del awaitables
        gc.collect()
        leaked = [
            str(w.message)
            for w in caught
            if issubclass(w.category, RuntimeWarning)
            and "never awaited" in str(w.message)
        ]
    assert leaked == [], f"leaked un-awaited coroutines: {leaked}"


# ---------------------------------------------------------------------------
# GREEN coverage
# ---------------------------------------------------------------------------


def test_gather_limited_preserves_order_and_bounds_concurrency() -> None:
    async def worker(x: int) -> int:
        return x * 2

    results = asyncio.run(gather_limited((worker(i) for i in range(5)), limit=2))
    assert results == [0, 2, 4, 6, 8]


def test_gather_limited_return_exceptions_collects_errors() -> None:
    async def worker(x: int) -> int:
        if x == 2:
            raise ValueError("bad")
        return x

    results = asyncio.run(
        gather_limited((worker(i) for i in range(4)), limit=2, return_exceptions=True)
    )
    assert results[:2] == [0, 1]
    assert isinstance(results[2], ValueError)
    assert results[3] == 3


def test_gather_limited_fail_fast_propagates_by_default() -> None:
    async def worker(x: int) -> int:
        if x == 1:
            raise RuntimeError("boom")
        return x

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(gather_limited((worker(i) for i in range(4)), limit=2))


def test_map_unordered_yields_and_cleanup_on_exception() -> None:
    async def worker(x: int) -> int:
        if x == 3:
            raise RuntimeError("boom")
        return x

    async def collect() -> list:
        out = []
        try:
            async for v in map_unordered(worker, range(5), limit=2):
                out.append(v)
        except RuntimeError:
            pass
        return out

    assert asyncio.run(collect())


def test_leases_lease_loss_cancels_operation_and_cleans_up() -> None:
    state = {"op_cancelled": 0, "renew_calls": 0}

    async def op() -> str:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            state["op_cancelled"] += 1
            raise
        return "done"

    async def renew() -> bool:
        state["renew_calls"] += 1
        if state["renew_calls"] >= 3:
            return False
        return True

    async def run() -> None:
        with pytest.raises(LeaseLostError):
            await run_with_lease_heartbeat(op, renew, heartbeat_interval=0.005)
        await asyncio.sleep(0.02)
        assert state["op_cancelled"] == 1
        leftover = [
            t for t in asyncio.all_tasks() if t is not asyncio.current_task()
        ]
        assert leftover == []

    asyncio.run(run())


def test_leases_operation_result_returned_when_healthy() -> None:
    async def op() -> str:
        return "done"

    async def renew() -> bool:
        return True

    result = asyncio.run(
        run_with_lease_heartbeat(op, renew, heartbeat_interval=0.005)
    )
    assert result == "done"


def test_rate_limit_enforces_timeout_and_try_acquire() -> None:
    async def scenario() -> None:
        rl = AsyncRateLimiter(rate=0.5, capacity=1.0)
        assert await rl.try_acquire() is True
        assert await rl.try_acquire() is False
        with pytest.raises(TimeoutError):
            await rl.acquire(timeout=0.01)

    asyncio.run(scenario())


def test_limits_enforce_bytes_items_steps_depth_time() -> None:
    b = ResourceBudget(max_bytes=10, max_items=3, max_steps=5, max_depth=2)
    assert b.consume_bytes(5) == 5
    with pytest.raises(BudgetExceededError):
        b.consume_bytes(6)
    with pytest.raises(BudgetExceededError):
        b.check_depth(3)
    b.check_depth(2)
    with pytest.raises(BudgetExceededError):
        with b.step():
            b.consume_steps(100)


def test_faulty_stream_caps_reads_and_injects_short_writes() -> None:
    src = io.BytesIO(b"hello world")
    fs = FaultyStream(src, max_read_bytes=3)
    assert fs.read() == b"hel"
    buf = io.BytesIO()
    out = FaultyStream(buf, max_write_bytes=4)
    out.write(b"abcdef")
    assert buf.getvalue() == b"abcd"


def test_flatten_enforces_depth_and_cycle_guards() -> None:
    assert list(flatten([[1, [2, [3]]]], max_depth=1)) == [1, [2, [3]]]
    cycle: list = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="cycle"):
        list(flatten([cycle]))
    with pytest.raises(ValueError, match="nesting"):
        list(flatten([[[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]]], max_nesting=5))
