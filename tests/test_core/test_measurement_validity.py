from __future__ import annotations

import unittest

from gunz_utils.benchmark.environment import capture_noise_info
from gunz_utils.benchmark.metrics import scaling_efficiency


class TestMeasurementValidity(unittest.TestCase):
    def test_scaling_efficiency(self) -> None:
        values = scaling_efficiency([1, 2, 4], [4.0, 2.0, 1.0])
        self.assertEqual(values, [1.0, 1.0, 1.0])

    def test_noise_capture_is_non_throwing(self) -> None:
        info = capture_noise_info()
        self.assertTrue(info.load_1m is None or info.load_1m >= 0)


if __name__ == "__main__":
    unittest.main()
