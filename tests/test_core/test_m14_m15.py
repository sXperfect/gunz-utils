from __future__ import annotations

import unittest

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
        clock.advance(2.5)
        self.assertEqual(clock.monotonic(), 2.5)

    def test_fuzz_is_reproducible(self) -> None:
        left = list(fuzz_integers(seed=42, count=100))
        right = list(fuzz_integers(seed=42, count=100))
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
