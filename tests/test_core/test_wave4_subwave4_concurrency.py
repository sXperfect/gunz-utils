"""Tests for Wave 4 Sub-Wave 4: Concurrency & Context (#40–#52)."""
from __future__ import annotations

import asyncio
import time
import pytest
from gunz_utils.concurrency import (
    AsyncWorkerPool,
    as_completed_limited,
    gather_limited,
    map_concurrent,
    run_in_thread,
)
from gunz_utils.context import (
    ExecutionContext,
    bind_context,
    correlation_id,
    get_context,
    operation_context,
    validate_correlation_id,
)


# =============================================================================
# #40–#47: Concurrency & Worker Pools
# =============================================================================

def test_gather_limited_and_map_concurrent_limit_validation():
    async def scenario():
        for bad_limit in (0, -1, True, False):
            with pytest.raises(ValueError, match="limit must be a positive integer"):
                await gather_limited([], limit=bad_limit)
            with pytest.raises(ValueError, match="limit must be a positive integer"):
                await map_concurrent(lambda x: x, [], limit=bad_limit)

    asyncio.run(scenario())


def test_async_worker_pool_lifecycle():
    async def scenario():
        pool = AsyncWorkerPool(limit=2)
        assert pool.limit == 2
        assert pool.pending_count == 0

        active = 0
        peak_active = 0

        async def worker(val: int):
            nonlocal active, peak_active
            active += 1
            if active > peak_active:
                peak_active = active
            await asyncio.sleep(0.02)
            active -= 1
            return val * 2

        tasks = [pool.submit(worker, i) for i in range(5)]
        assert pool.pending_count > 0

        await pool.join()
        assert pool.pending_count == 0
        assert peak_active <= 2
        results = [t.result() for t in tasks]
        assert results == [0, 2, 4, 6, 8]

        await pool.close()
        with pytest.raises(RuntimeError, match="AsyncWorkerPool is closed"):
            pool.submit(worker, 10)

    asyncio.run(scenario())


def test_async_worker_pool_context_manager():
    async def scenario():
        results = []

        async def job(v: int):
            await asyncio.sleep(0.01)
            results.append(v)

        async with AsyncWorkerPool(limit=3) as pool:
            for i in range(3):
                pool.submit(job, i)

        # Context manager automatically joined on exit
        assert sorted(results) == [0, 1, 2]

    asyncio.run(scenario())


def test_run_in_thread():
    async def scenario():
        def blocking_calc(x: int, y: int) -> int:
            time.sleep(0.01)
            return x + y

        res = await run_in_thread(blocking_calc, 10, 25)
        assert res == 35

    asyncio.run(scenario())


def test_as_completed_limited():
    async def scenario():
        async def work(val: int, delay: float):
            await asyncio.sleep(delay)
            return val

        # 3 tasks with different delays
        coros = [work(1, 0.04), work(2, 0.01), work(3, 0.02)]
        results = []
        async for r in as_completed_limited(coros, limit=2):
            results.append(r)

        # 2 completes first (0.01), then 3 (0.02), then 1 (0.04)
        assert results == [2, 3, 1]

    asyncio.run(scenario())


# =============================================================================
# #48–#52: Execution Context & Validation
# =============================================================================

def test_bind_context_and_get_context():
    assert get_context("request_id") is None
    assert get_context() == {}

    with bind_context(request_id="req-123", tenant="alpha") as ctx:
        assert ctx["request_id"] == "req-123"
        assert get_context("request_id") == "req-123"
        assert get_context("tenant") == "alpha"
        assert get_context()["request_id"] == "req-123"

        # Nested scope override
        with bind_context(tenant="beta"):
            assert get_context("tenant") == "beta"
            assert get_context("request_id") == "req-123"

        # Restored after nested exit
        assert get_context("tenant") == "alpha"

    # Restored after outer exit
    assert get_context("request_id") is None


def test_execution_context_container():
    with operation_context("cid-456"):
        with bind_context(user="alice"):
            ctx = ExecutionContext()
            assert ctx.correlation_id == "cid-456"
            assert ctx.data["user"] == "alice"
            assert ctx.get("user") == "alice"
            assert ctx["user"] == "alice"
            assert "user" in ctx
            assert "missing" not in ctx
            assert repr(ctx) == "ExecutionContext(correlation_id='cid-456', data={'user': 'alice'})"


def test_validate_correlation_id():
    assert validate_correlation_id("abc-123_XYZ:1.0/test") is True

    with pytest.raises(TypeError, match="must be a string"):
        validate_correlation_id(123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="non-empty"):
        validate_correlation_id("")

    with pytest.raises(ValueError, match="non-empty"):
        validate_correlation_id("   ")

    with pytest.raises(ValueError, match="invalid character"):
        validate_correlation_id("hello world!")

    with pytest.raises(ValueError, match="128 characters"):
        validate_correlation_id("x" * 129)
