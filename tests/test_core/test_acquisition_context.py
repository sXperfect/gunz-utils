from __future__ import annotations

import asyncio
import unittest

from gunz_utils.context import correlation_id, ensure_correlation_id, operation_context
from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.resilience import AsyncBulkhead
from gunz_utils.testing import eventually_async


class TestContext(unittest.IsolatedAsyncioTestCase):
    async def test_context_propagates_and_restores(self) -> None:
        self.assertIsNone(correlation_id())
        with operation_context("request-1"):
            self.assertEqual(correlation_id(), "request-1")

            async def child() -> str | None:
                await asyncio.sleep(0)
                return correlation_id()

            self.assertEqual(await asyncio.create_task(child()), "request-1")
        self.assertIsNone(correlation_id())

    async def test_ensure_correlation_id_is_stable(self) -> None:
        first = ensure_correlation_id()
        self.assertEqual(ensure_correlation_id(), first)


class TestAcquisition(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limiter_try_acquire(self) -> None:
        limiter = AsyncRateLimiter(1, capacity=1)
        self.assertTrue(await limiter.try_acquire())
        self.assertFalse(await limiter.try_acquire())

    async def test_rate_limiter_timeout(self) -> None:
        limiter = AsyncRateLimiter(1, capacity=1)
        await limiter.acquire()
        with self.assertRaises(TimeoutError):
            await limiter.acquire(timeout=0)

    async def test_bulkhead_timeout(self) -> None:
        bulkhead = AsyncBulkhead(1)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def hold() -> None:
            entered.set()
            await release.wait()

        task = asyncio.create_task(bulkhead.run(hold))
        await entered.wait()
        with self.assertRaises(TimeoutError):
            await bulkhead.run(lambda: asyncio.sleep(0), timeout=0)
        release.set()
        await task


class TestAsyncTesting(unittest.IsolatedAsyncioTestCase):
    async def test_eventually_async(self) -> None:
        calls = 0

        async def predicate() -> bool:
            nonlocal calls
            calls += 1
            return calls >= 2

        await eventually_async(predicate, timeout=1, interval=0.001)
        self.assertEqual(calls, 2)

    async def test_eventually_async_timeout(self) -> None:
        """A false predicate must terminate when its deadline expires."""
        async def predicate() -> bool:
            return False

        with self.assertRaises(TimeoutError):
            await eventually_async(predicate, timeout=0)

    async def test_eventually_async_invalid_timing(self) -> None:
        """Reject invalid timing before invoking the predicate."""
        async def predicate() -> bool:
            self.fail("invalid timing must not invoke the predicate")

        for timeout, interval in [(-1, 0.01), (1, 0), (1, -1)]:
            with self.subTest(timeout=timeout, interval=interval):
                with self.assertRaises(ValueError):
                    await eventually_async(
                        predicate, timeout=timeout, interval=interval
                    )


if __name__ == "__main__":
    unittest.main()
