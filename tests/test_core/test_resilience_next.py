from __future__ import annotations

import asyncio
import math
import unittest

from gunz_utils.cache import CacheInfo, ttl_cache
from gunz_utils.concurrency import map_unordered
from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.result import Result
from gunz_utils.retry import RetryPolicy, async_retry, retry


class TestResultOperations(unittest.TestCase):
    def test_map_and_fallback(self) -> None:
        ok = Result[int, str].ok(2)
        self.assertEqual(ok.map(lambda value: value * 3).unwrap(), 6)
        self.assertEqual(Result[int, str].err("x").unwrap_or(4), 4)

    def test_map_error(self) -> None:
        err = Result[int, str].err("bad").map_error(str.upper)
        self.assertEqual(err.error, "BAD")


class TestCacheInfo(unittest.TestCase):
    def test_cache_info_and_clear(self) -> None:
        @ttl_cache(ttl=60, maxsize=2)
        def work(value: int) -> int:
            return value

        work(1)
        work(1)
        info = work.cache_info()
        self.assertEqual(info, CacheInfo(hits=1, misses=1, size=1, maxsize=2))
        work.cache_clear()
        self.assertEqual(
            work.cache_info(), CacheInfo(hits=0, misses=0, size=0, maxsize=2)
        )


class TestRetryPolicy(unittest.TestCase):
    def test_rejects_non_finite_and_boolean_timing(self) -> None:
        invalid = (math.nan, math.inf, -math.inf, True)
        for value in invalid:
            with self.subTest(base_delay=value):
                with self.assertRaises(ValueError):
                    RetryPolicy(base_delay=value)
            with self.subTest(max_delay=value):
                with self.assertRaises(ValueError):
                    RetryPolicy(max_delay=value)
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    RetryPolicy(timeout=value)

        with self.assertRaises(ValueError):
            RetryPolicy(attempts=True)

    def test_predicate_stops_retry(self) -> None:
        calls = 0

        @retry(attempts=3, base_delay=0, retry_if=lambda exc: False)
        def work() -> None:
            nonlocal calls
            calls += 1
            raise ValueError("permanent")

        with self.assertRaises(ValueError):
            work()
        self.assertEqual(calls, 1)

    def test_hook_receives_retry(self) -> None:
        events: list[tuple[int, float]] = []
        calls = 0

        @retry(
            attempts=2,
            base_delay=0,
            jitter=False,
            on_retry=lambda exc, attempt, delay: events.append((attempt, delay)),
        )
        def work() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("temporary")
            return "ok"

        self.assertEqual(work(), "ok")
        self.assertEqual(events, [(1, 0)])


class TestAsyncResilience(unittest.IsolatedAsyncioTestCase):
    async def test_map_unordered_is_bounded(self) -> None:
        active = 0
        peak = 0

        async def work(value: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001 * (4 - value))
            active -= 1
            return value

        result = [value async for value in map_unordered(work, range(4), limit=2)]
        self.assertEqual(set(result), set(range(4)))
        self.assertLessEqual(peak, 2)

    async def test_async_retry_predicate(self) -> None:
        calls = 0

        @async_retry(attempts=3, base_delay=0, retry_if=lambda exc: False)
        async def work() -> None:
            nonlocal calls
            calls += 1
            raise ValueError("permanent")

        with self.assertRaises(ValueError):
            await work()
        self.assertEqual(calls, 1)

    async def test_rate_limiter_reports_capacity(self) -> None:
        limiter = AsyncRateLimiter(10, capacity=2)
        self.assertLessEqual(limiter.available_tokens, 2)
        await limiter.acquire()
        self.assertLess(limiter.available_tokens, 2)

    async def test_rate_limiter_rejects_non_finite_parameters(self) -> None:
        invalid = (math.nan, math.inf, -math.inf, True)
        for value in invalid:
            with self.subTest(rate=value):
                with self.assertRaises(ValueError):
                    AsyncRateLimiter(value)
            with self.subTest(capacity=value):
                with self.assertRaises(ValueError):
                    AsyncRateLimiter(1, capacity=value)

        limiter = AsyncRateLimiter(1, capacity=2)
        for value in invalid:
            with self.subTest(tokens=value):
                with self.assertRaises(ValueError):
                    await limiter.try_acquire(value)
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    await limiter.acquire(timeout=value)
