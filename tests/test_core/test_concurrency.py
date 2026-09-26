from __future__ import annotations

import asyncio
import unittest

from gunz_utils.concurrency import gather_limited, map_concurrent


class TestConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_map_preserves_order_and_limit(self) -> None:
        active = 0
        peak = 0

        async def work(value: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001)
            active -= 1
            return value * 2

        self.assertEqual(
            await map_concurrent(work, range(6), limit=2),
            [0, 2, 4, 6, 8, 10],
        )
        self.assertLessEqual(peak, 2)

    async def test_return_exceptions(self) -> None:
        async def fail() -> int:
            raise ValueError("x")

        result = await gather_limited([fail()], limit=1, return_exceptions=True)
        self.assertIsInstance(result[0], ValueError)

    async def test_invalid_limit(self) -> None:
        with self.assertRaises(ValueError):
            await gather_limited([], limit=0)
