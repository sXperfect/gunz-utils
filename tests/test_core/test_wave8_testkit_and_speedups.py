"""Tests for Wave 8: Testkit, timing, testing helpers, and suite speedups."""

from __future__ import annotations

import asyncio
import math
import sys
from unittest import IsolatedAsyncioTestCase, TestCase

from gunz_utils.testkit import (
    ManualClock,
    fuzz_bytes,
    fuzz_floats,
    fuzz_integers,
    fuzz_json_objects,
    fuzz_primitives,
    fuzz_strings,
)
from gunz_utils.testing import eventually, eventually_async
from gunz_utils.time_utils import expired, monotonic_deadline, remaining
from gunz_utils.timing import Timer, timer


class Wave8TestkitFuzzValidationTest(TestCase):
    def test_manual_clock_validation(self) -> None:
        clock = ManualClock(now=123.45)
        self.assertEqual(clock.monotonic(), 123.45)
        clock.advance(10.0)
        self.assertEqual(clock.monotonic(), 133.45)

        with self.assertRaises(TypeError):
            ManualClock(now=True)
        with self.assertRaises(TypeError):
            ManualClock(now=float("nan"))
        with self.assertRaises(TypeError):
            ManualClock(now=float("inf"))

    def test_fuzz_generators_seed_validation(self) -> None:
        with self.assertRaises(TypeError):
            list(fuzz_integers(seed=True, count=5))
        with self.assertRaises(TypeError):
            list(fuzz_integers(seed="bad", count=5))
        with self.assertRaises(TypeError):
            list(fuzz_floats(seed=False, count=5))
        with self.assertRaises(TypeError):
            list(fuzz_strings(seed=True, count=5))
        with self.assertRaises(TypeError):
            list(fuzz_bytes(seed="bad", count=5))
        with self.assertRaises(TypeError):
            list(fuzz_primitives(seed=True, count=5))
        with self.assertRaises(TypeError):
            list(fuzz_json_objects(seed="bad", count=5))

    def test_fuzz_floats_extreme_range(self) -> None:
        # Extreme range where max_f - min_f is infinite
        min_val = -1e308
        max_val = 1e308
        samples = list(
            fuzz_floats(
                seed=42,
                count=20,
                minimum=min_val,
                maximum=max_val,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        self.assertEqual(len(samples), 20)
        for s in samples:
            self.assertTrue(math.isfinite(s))
            self.assertTrue(min_val <= s <= max_val)


class Wave8TestingHelpersTest(IsolatedAsyncioTestCase):
    def test_eventually_validation_and_behavior(self) -> None:
        with self.assertRaises(TypeError):
            eventually("not_callable")  # type: ignore[arg-type]

        counter = 0

        def cond() -> bool:
            nonlocal counter
            counter += 1
            return counter >= 3

        eventually(cond, timeout=1.0, interval=0.005)
        self.assertGreaterEqual(counter, 3)

        # Timeout overshoot clamp
        with self.assertRaises(TimeoutError):
            eventually(lambda: False, timeout=0.02, interval=0.5)

    async def test_eventually_async_validation_and_behavior(self) -> None:
        with self.assertRaises(TypeError):
            await eventually_async("not_callable")  # type: ignore[arg-type]

        counter = 0

        async def cond() -> bool:
            nonlocal counter
            counter += 1
            return counter >= 3

        await eventually_async(cond, timeout=1.0, interval=0.005)
        self.assertGreaterEqual(counter, 3)

        with self.assertRaises(TimeoutError):
            async def never() -> bool:
                return False

            await eventually_async(never, timeout=0.02, interval=0.5)


class Wave8TimeUtilsAndTimingTest(TestCase):
    def test_time_utils_custom_clock(self) -> None:
        fake_time = 100.0

        def fake_clock() -> float:
            return fake_time

        dl = monotonic_deadline(10.0, clock=fake_clock)
        self.assertEqual(dl, 110.0)

        self.assertEqual(remaining(110.0, clock=fake_clock), 10.0)
        self.assertFalse(expired(110.0, clock=fake_clock))

        fake_time = 115.0
        self.assertEqual(remaining(110.0, clock=fake_clock), 0.0)
        self.assertTrue(expired(110.0, clock=fake_clock))

        with self.assertRaises(TypeError):
            monotonic_deadline(5.0, clock="not_callable")  # type: ignore[arg-type]

        with self.assertRaises(OverflowError):
            monotonic_deadline(sys.float_info.max, clock=lambda: sys.float_info.max)

    def test_timer_custom_clock_and_reset(self) -> None:
        current_time = 50.0

        def clock() -> float:
            return current_time

        t = Timer(auto_start=False, clock=clock)
        self.assertEqual(t.elapsed, 0.0)

        t.start()
        current_time = 55.5
        self.assertEqual(t.elapsed, 5.5)

        t.stop()
        current_time = 60.0
        self.assertEqual(t.elapsed, 5.5)

        t.reset()
        self.assertEqual(t.elapsed, 0.0)

        with self.assertRaises(TypeError):
            Timer(auto_start="not_bool")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            Timer(clock="not_callable")  # type: ignore[arg-type]

        with timer(clock=clock) as t2:
            current_time = 70.0
        self.assertEqual(t2.elapsed, 10.0)
