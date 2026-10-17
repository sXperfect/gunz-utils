# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import unittest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.limits import Limits
from gunz_utils.testkit import ManualClock, fuzz_integers


class TestM14M15(unittest.TestCase):
    def test_limits(self) -> None:
        limits = Limits(max_bytes=10, max_items=2)
        limits.check_bytes(10)
        with self.assertRaises(ValueError):
            limits.check_bytes(11)
        with self.assertRaises(ValueError):
            limits.check_items(3)

    def test_manual_clock(self) -> None:
        clock = ManualClock()
        self.assertEqual(clock.monotonic(), 0.0)
        clock.advance(0.0)
        self.assertEqual(clock.monotonic(), 0.0)
        clock.advance(2.5)
        self.assertEqual(clock.monotonic(), 2.5)

    def test_manual_clock_rejects_non_finite_advance(self) -> None:
        clock = ManualClock()
        for value in (math.nan, math.inf, -math.inf, True, -1.0, -0.01):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    clock.advance(value)

    def test_manual_clock_overflow_raises_error(self) -> None:
        clock = ManualClock(now=1e308)
        with self.assertRaises(OverflowError):
            clock.advance(1e308)

    def test_fuzz_validates_integer_domain(self) -> None:
        with self.assertRaises(ValueError):
            list(fuzz_integers(seed=1, count=True))
        with self.assertRaises(ValueError):
            list(fuzz_integers(seed=1, count=-1))
        with self.assertRaises(ValueError):
            list(fuzz_integers(seed=1, count=1, minimum=True))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            list(fuzz_integers(seed=1, count=1, maximum=True))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            list(fuzz_integers(seed=1, count=1, minimum=2, maximum=1))

    def test_fuzz_boundary_counts_and_ranges(self) -> None:
        self.assertEqual(list(fuzz_integers(seed=1, count=0)), [])
        singleton = list(fuzz_integers(seed=1, count=5, minimum=7, maximum=7))
        self.assertEqual(singleton, [7, 7, 7, 7, 7])

    def test_fuzz_is_reproducible(self) -> None:
        left = list(fuzz_integers(seed=42, count=100))
        right = list(fuzz_integers(seed=42, count=100))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
