from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime, timedelta

from gunz_utils.cache import RecencyTTLPolicy, SingleFlight, ttl_cache


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


    def test_unhashable_arguments_bypass_cache(self) -> None:
        calls = 0

        @ttl_cache(ttl=60)
        def work(value: list[int]) -> int:
            nonlocal calls
            calls += 1
            return len(value)

        self.assertEqual(work([1]), 1)
        self.assertEqual(work([1]), 1)
        self.assertEqual(calls, 2)


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



class TestRecencyTTLPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = RecencyTTLPolicy(
            recent_window=timedelta(days=5),
            recent_ttl=timedelta(hours=6),
            historical_ttl=timedelta(days=30),
            empty_recent_ttl=timedelta(hours=1),
        )
        self.now = datetime(
            2026,
            9,
            27,
            12,
            0,
            tzinfo=UTC,
        )

    def test_selects_recent_and_historical_ttls(self) -> None:
        self.assertEqual(
            self.policy.ttl_for(
                self.now - timedelta(days=2),
                now=self.now,
            ),
            timedelta(hours=6),
        )
        self.assertEqual(
            self.policy.ttl_for(
                self.now - timedelta(days=10),
                now=self.now,
            ),
            timedelta(days=30),
        )

    def test_recent_empty_result_uses_empty_ttl(self) -> None:
        self.assertEqual(
            self.policy.ttl_for(
                self.now - timedelta(hours=2),
                empty=True,
                now=self.now,
            ),
            timedelta(hours=1),
        )

    def test_future_timestamp_is_treated_as_recent(self) -> None:
        self.assertEqual(
            self.policy.ttl_for(
                self.now + timedelta(hours=1),
                now=self.now,
            ),
            timedelta(hours=6),
        )

    def test_requires_timezone_aware_datetimes(self) -> None:
        naive = datetime(2026, 9, 27, 12, 0)

        with self.assertRaises(ValueError):
            self.policy.ttl_for(
                naive,
                now=self.now,
            )
        with self.assertRaises(ValueError):
            self.policy.ttl_for(
                self.now,
                now=naive,
            )

    def test_rejects_negative_durations(self) -> None:
        with self.assertRaises(ValueError):
            RecencyTTLPolicy(
                recent_window=timedelta(days=-1),
                recent_ttl=timedelta(hours=1),
                historical_ttl=timedelta(days=1),
            )
