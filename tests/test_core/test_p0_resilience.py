from __future__ import annotations

import asyncio
import unittest

from gunz_utils.cache import CacheInfo, async_ttl_cache, ttl_cache
from gunz_utils.concurrency import gather_limited
from gunz_utils.resilience import AsyncBulkhead, AsyncCircuitBreaker, CircuitState
from gunz_utils.retry import async_retry, retry


class TestBoundedConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_gather_consumes_input_lazily(self) -> None:
        consumed = 0
        gate = asyncio.Event()

        async def work(value: int) -> int:
            await gate.wait()
            return value

        def source():
            nonlocal consumed
            for value in range(100):
                consumed += 1
                yield work(value)

        task = asyncio.create_task(gather_limited(source(), limit=3))
        await asyncio.sleep(0)
        self.assertEqual(consumed, 3)
        gate.set()
        result = await task
        self.assertEqual(result, list(range(100)))


class TestCacheP0(unittest.TestCase):
    def test_typed_cache_info(self) -> None:
        @ttl_cache(ttl=60)
        def work(value: int) -> int:
            return value

        work(1)
        work(1)
        info = work.cache_info()
        self.assertIsInstance(info, CacheInfo)
        self.assertEqual((info.hits, info.misses), (1, 1))


class TestAsyncCache(unittest.IsolatedAsyncioTestCase):
    async def test_coalesces_concurrent_misses(self) -> None:
        calls = 0

        @async_ttl_cache(ttl=60)
        async def work(value: int) -> int:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return value * 2

        result = await asyncio.gather(work(3), work(3), work(3))
        self.assertEqual(result, [6, 6, 6])
        self.assertEqual(calls, 1)


class TestRetryBudget(unittest.IsolatedAsyncioTestCase):
    async def test_sync_budget_prevents_sleep_past_deadline(self) -> None:
        calls = 0

        @retry(attempts=10, base_delay=1, jitter=False, timeout=0)
        def work() -> None:
            nonlocal calls
            calls += 1
            raise OSError("down")

        with self.assertRaises(OSError):
            work()
        self.assertEqual(calls, 1)

    async def test_async_budget_prevents_sleep_past_deadline(self) -> None:
        calls = 0

        @async_retry(attempts=10, base_delay=1, jitter=False, timeout=0)
        async def work() -> None:
            nonlocal calls
            calls += 1
            raise OSError("down")

        with self.assertRaises(OSError):
            await work()
        self.assertEqual(calls, 1)


class TestResilienceP0(unittest.IsolatedAsyncioTestCase):
    async def test_breaker_ignores_filtered_failure(self) -> None:
        breaker = AsyncCircuitBreaker(
            failure_threshold=1,
            failure_predicate=lambda exc: isinstance(exc, OSError),
        )

        async def caller_error() -> None:
            raise ValueError("bad request")

        with self.assertRaises(ValueError):
            await breaker.call(caller_error)
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    async def test_bulkhead_available_tracks_activity(self) -> None:
        bulkhead = AsyncBulkhead(1)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def work() -> None:
            entered.set()
            await release.wait()

        task = asyncio.create_task(bulkhead.run(work))
        await entered.wait()
        self.assertEqual(bulkhead.available, 0)
        release.set()
        await task
        self.assertEqual(bulkhead.available, 1)
