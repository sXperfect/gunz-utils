from __future__ import annotations

import asyncio
import unittest

from gunz_utils.cache import SingleFlight, ttl_cache


class TestTTLCache(unittest.TestCase):
    def test_cache_hit(self) -> None:
        calls = 0

        @ttl_cache(ttl=60)
        def work(value: int) -> int:
            nonlocal calls
            calls += 1
            return value * 2

        self.assertEqual(work(2), 4)
        self.assertEqual(work(2), 4)
        self.assertEqual(calls, 1)


class TestSingleFlight(unittest.IsolatedAsyncioTestCase):
    async def test_coalesces_same_key(self) -> None:
        flight = SingleFlight()
        calls = 0

        async def work() -> int:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return 7

        results = await asyncio.gather(
            flight.run("same", work),
            flight.run("same", work),
            flight.run("same", work),
        )
        self.assertEqual(results, [7, 7, 7])
        self.assertEqual(calls, 1)
