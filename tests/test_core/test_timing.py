"""Tests for elapsed-time measurement utilities."""

from __future__ import annotations

import time
import unittest

from gunz_utils import Timer, timer


class TimerTests(unittest.TestCase):
    def test_context_manager_measures_elapsed(self) -> None:
        with Timer() as timed:
            time.sleep(0.01)
        self.assertGreaterEqual(timed.elapsed, 0.01)

    def test_label_attribute_is_preserved(self) -> None:
        with Timer("foo") as timed:
            pass
        self.assertEqual(timed.label, "foo")

    def test_manual_start_and_stop(self) -> None:
        timed = Timer(auto_start=False)
        timed.start()
        time.sleep(0.01)
        timed.stop()
        self.assertGreater(timed.elapsed, 0.0)

    def test_elapsed_before_start_is_zero(self) -> None:
        timed = Timer(auto_start=False)
        self.assertEqual(timed.elapsed, 0.0)

    def test_elapsed_while_running(self) -> None:
        timed = Timer()
        time.sleep(0.01)
        self.assertGreaterEqual(timed.elapsed, 0.01)
        self.assertLess(timed.elapsed, 0.5)

    def test_elapsed_after_stop_is_fixed(self) -> None:
        timed = Timer()
        timed.stop()
        first = timed.elapsed
        time.sleep(0.01)
        self.assertEqual(first, timed.elapsed)

    def test_context_exit_stops_timer(self) -> None:
        with Timer() as timed:
            pass
        self.assertIsNotNone(timed._end_time)

    def test_context_exit_does_not_suppress_exceptions(self) -> None:
        with self.assertRaises(ValueError):
            with Timer() as timed:
                raise ValueError("expected")
        self.assertIsNotNone(timed._end_time)

    def test_timer_context_manager(self) -> None:
        with timer("x") as timed:
            pass
        self.assertEqual(timed.label, "x")
        self.assertIsNotNone(timed._end_time)

    def test_start_restarts_timer(self) -> None:
        timed = Timer()
        timed.stop()
        timed.start()
        self.assertIsNone(timed._end_time)


if __name__ == "__main__":
    unittest.main()
