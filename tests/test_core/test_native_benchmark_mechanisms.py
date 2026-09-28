from __future__ import annotations

import math
import sys
import unittest

from gunz_utils.benchmark import (
    analyze_stability,
    benchmark,
    calibrate_loops,
    profile_command,
)


class TestNativeBenchmarkMechanisms(unittest.TestCase):
    def test_calibration(self) -> None:
        loops = calibrate_loops(lambda: None, target_time=0.0001)
        self.assertGreaterEqual(loops, 1)

    def test_calibration_rejects_invalid_numeric_domain(self) -> None:
        for value in (0.0, -1.0, math.nan, math.inf, -math.inf, True):
            with self.subTest(target_time=value):
                with self.assertRaises(ValueError):
                    calibrate_loops(lambda: None, target_time=value)

        for value in (0, -1, True):
            with self.subTest(max_loops=value):
                with self.assertRaises(ValueError):
                    calibrate_loops(lambda: None, max_loops=value)

    def test_benchmark_records_loops(self) -> None:
        result = benchmark(
            lambda: None,
            warmup=0,
            iterations=4,
            target_time=0.0001,
        )
        self.assertGreaterEqual(result.parameters["_loops"], 1)
        report = analyze_stability(result)
        self.assertGreaterEqual(report.coefficient_of_variation, 0)

    def test_stability_rejects_invalid_thresholds(self) -> None:
        result = benchmark(
            lambda: None,
            warmup=0,
            iterations=2,
            loops=1,
        )
        for value in (-1.0, math.nan, math.inf, -math.inf, True):
            with self.subTest(max_cv=value):
                with self.assertRaises(ValueError):
                    analyze_stability(result, max_cv=value)
            with self.subTest(max_relative_range=value):
                with self.assertRaises(ValueError):
                    analyze_stability(
                        result,
                        max_relative_range=value,
                    )

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux /proc required")
    def test_rss_only_profile(self) -> None:
        profile = profile_command(
            [sys.executable, "-c", "sum(range(10000))"],
            interval=0.001,
            memory_detail="rss",
            check=True,
        )
        self.assertIsNone(profile.peak_pss_bytes)
        self.assertIsNone(profile.peak_private_bytes)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux /proc required")
    def test_sparse_detailed_memory_sampling(self) -> None:
        profile = profile_command(
            [sys.executable, "-c", "import time;time.sleep(.02)"],
            interval=0.001,
            memory_detail="pss",
            detailed_memory_every=5,
            check=True,
        )
        self.assertGreaterEqual(len(profile.samples), 1)


if __name__ == "__main__":
    unittest.main()
