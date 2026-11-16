"""Tests for Wave 4 Sub-Wave 1: timing, stopwatches, and deadlines (#1–#13)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import unittest
from datetime import UTC, datetime

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.time_utils import (
    clamp_datetime,
    from_iso_utc,
    from_unix_millis,
    from_unix_seconds,
    is_aware,
    to_iso_utc,
    to_unix_millis,
    to_unix_seconds,
)
from gunz_utils.timing import LapRecord, Stopwatch, Timer, async_timer


class MockClock:
    def __init__(self,
        start: float = 1000.0,
    ) -> None:
        self.time = start

    def __call__(self) -> float:
        return self.time

    def advance(self,
        delta: float,
    ) -> None:
        self.time += delta


class TestWave4SubWave1Timing(unittest.IsolatedAsyncioTestCase):
    def test_item1_timer_is_running(self) -> None:
        clock = MockClock()
        t = Timer(auto_start=False, clock=clock)
        self.assertFalse(t.is_running)

        t.start()
        self.assertTrue(t.is_running)

        t.stop()
        self.assertFalse(t.is_running)

    def test_item2_timer_unit_properties(self) -> None:
        clock = MockClock()
        t = Timer(clock=clock)
        clock.advance(1.5)
        self.assertAlmostEqual(t.elapsed, 1.5)
        self.assertAlmostEqual(t.elapsed_ms, 1500.0)
        self.assertAlmostEqual(t.elapsed_us, 1_500_000.0)
        self.assertEqual(t.elapsed_ns, 1_500_000_000)

    def test_item3_timer_lap_recording(self) -> None:
        clock = MockClock()
        t = Timer(clock=clock)
        clock.advance(1.0)
        split1 = t.lap("first")
        self.assertAlmostEqual(split1, 1.0)

        clock.advance(2.0)
        split2 = t.lap("second")
        self.assertAlmostEqual(split2, 2.0)

        self.assertEqual(len(t.laps), 2)
        self.assertEqual(t.laps[0], LapRecord(1, "first", 1.0, 1.0))
        self.assertEqual(t.laps[1], LapRecord(2, "second", 2.0, 3.0))

    def test_item4_timer_pause_and_resume(self) -> None:
        clock = MockClock()
        t = Timer(clock=clock)
        clock.advance(1.0)
        t.pause()
        self.assertTrue(t.is_paused)
        self.assertFalse(t.is_running)
        self.assertAlmostEqual(t.elapsed, 1.0)

        #? Elapsed should not advance while paused
        clock.advance(5.0)
        self.assertAlmostEqual(t.elapsed, 1.0)

        t.resume()
        self.assertFalse(t.is_paused)
        self.assertTrue(t.is_running)
        clock.advance(2.0)
        self.assertAlmostEqual(t.elapsed, 3.0)

    async def test_item5_timer_async_context_manager(self) -> None:
        clock = MockClock()
        t = Timer(auto_start=False, clock=clock)
        async with t:
            self.assertTrue(t.is_running)
            clock.advance(2.5)
        self.assertFalse(t.is_running)
        self.assertAlmostEqual(t.elapsed, 2.5)

    async def test_item6_async_timer_helper(self) -> None:
        clock = MockClock()
        async with async_timer("async-op", clock=clock) as t:
            self.assertEqual(t.label, "async-op")
            clock.advance(0.75)
        self.assertAlmostEqual(t.elapsed, 0.75)

    def test_item7_stopwatch_multi_interval(self) -> None:
        clock = MockClock()
        sw = Stopwatch(clock=clock)
        self.assertFalse(sw.is_running)
        self.assertEqual(sw.count, 0)
        self.assertEqual(sw.total_elapsed, 0.0)

        sw.start()
        clock.advance(2.0)
        interval1 = sw.stop()
        self.assertAlmostEqual(interval1, 2.0)

        clock.advance(10.0)  #? dead time between intervals

        sw.start()
        clock.advance(4.0)
        interval2 = sw.stop()
        self.assertAlmostEqual(interval2, 4.0)

        self.assertEqual(sw.count, 2)
        self.assertAlmostEqual(sw.total_elapsed, 6.0)
        self.assertAlmostEqual(sw.mean_elapsed, 3.0)

        #? Context manager
        with sw:
            clock.advance(3.0)
        self.assertEqual(sw.count, 3)
        self.assertAlmostEqual(sw.total_elapsed, 9.0)


class TestWave4SubWave1TimeUtils(unittest.TestCase):
    def test_item8_to_iso_utc(self) -> None:
        dt_naive = datetime(2026, 11, 10, 14, 30, 0)
        self.assertEqual(to_iso_utc(dt_naive), "2026-11-10T14:30:00Z")

        dt_micro = datetime(2026, 11, 10, 14, 30, 0, 123456, tzinfo=UTC)
        self.assertEqual(to_iso_utc(dt_micro), "2026-11-10T14:30:00.123456Z")

    def test_item9_from_iso_utc(self) -> None:
        iso_str = "2026-11-10T14:30:00Z"
        parsed = from_iso_utc(iso_str)
        self.assertTrue(is_aware(parsed))
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.hour, 14)

        with self.assertRaises(ValueError):
            from_iso_utc("invalid-date-string")
        with self.assertRaises(TypeError):
            from_iso_utc(123)  # type: ignore[arg-type]

    def test_item10_unix_seconds_converters(self) -> None:
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        sec = to_unix_seconds(now)
        reconstructed = from_unix_seconds(sec)
        self.assertEqual(now, reconstructed)

        with self.assertRaises(ValueError):
            from_unix_seconds(float("nan"))
        with self.assertRaises(ValueError):
            from_unix_seconds(float("inf"))

    def test_item11_unix_millis_converters(self) -> None:
        now = datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=UTC)
        ms = to_unix_millis(now)
        reconstructed = from_unix_millis(ms)
        self.assertEqual(now, reconstructed)

    def test_item12_is_aware_and_clamp_datetime(self) -> None:
        naive = datetime(2026, 1, 1)
        aware = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertFalse(is_aware(naive))
        self.assertTrue(is_aware(aware))

        min_dt = datetime(2026, 1, 1, tzinfo=UTC)
        max_dt = datetime(2026, 1, 31, tzinfo=UTC)
        early = datetime(2025, 12, 1, tzinfo=UTC)
        late = datetime(2026, 2, 1, tzinfo=UTC)
        mid = datetime(2026, 1, 15, tzinfo=UTC)

        self.assertEqual(clamp_datetime(early, min_dt, max_dt), min_dt)
        self.assertEqual(clamp_datetime(late, min_dt, max_dt), max_dt)
        self.assertEqual(clamp_datetime(mid, min_dt, max_dt), mid)


if __name__ == "__main__":
    unittest.main()
