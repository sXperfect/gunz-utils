from __future__ import annotations

import math
import unittest

from gunz_utils.benchmark.environment import capture_noise_info
from gunz_utils.benchmark.metrics import scaling_efficiency


class TestMeasurementValidity(unittest.TestCase):
    def test_scaling_efficiency(self) -> None:
        values = scaling_efficiency([1, 2, 4], [4.0, 2.0, 1.0])
        self.assertEqual(values, [1.0, 1.0, 1.0])

    def test_scaling_efficiency_rejects_invalid_baseline(self) -> None:
        for workers, durations in (
            ([0, 2], [4.0, 2.0]),
            ([1, 2], [0.0, 2.0]),
            ([1, 2], [math.nan, 2.0]),
            ([1, 2], [math.inf, 2.0]),
        ):
            with self.subTest(workers=workers, durations=durations):
                with self.assertRaises(ValueError):
                    scaling_efficiency(workers, durations)

    def test_scaling_efficiency_marks_invalid_nonbaseline_point(self) -> None:
        self.assertEqual(
            scaling_efficiency([1, 2, 0], [4.0, 2.0, 1.0]),
            [1.0, 1.0, None],
        )
        values = scaling_efficiency(
            [1, 2, 4],
            [4.0, math.nan, 1.0],
        )
        self.assertEqual(values[0], 1.0)
        self.assertIsNone(values[1])
        self.assertEqual(values[2], 1.0)

    def test_noise_capture_is_non_throwing(self) -> None:
        info = capture_noise_info()
        self.assertTrue(info.load_1m is None or info.load_1m >= 0)


if __name__ == "__main__":
    unittest.main()
