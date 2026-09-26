from __future__ import annotations

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
