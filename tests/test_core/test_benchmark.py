from __future__ import annotations

import json
import math
import sys
import unittest

from gunz_utils.benchmark import benchmark, compare_results, profile_command


class TestBenchmark(unittest.TestCase):
    def test_runner_captures_samples_and_stats(self) -> None:
        result = benchmark(lambda: sum(range(10)), warmup=1, iterations=4)
        self.assertEqual(len(result.samples), 4)
        self.assertEqual(result.iterations, 4)
        self.assertGreaterEqual(result.stats.maximum, result.stats.minimum)
        json.dumps(result.to_dict())

    def test_comparison_detects_regression(self) -> None:
        baseline = benchmark(lambda: None, iterations=2, warmup=0)
        candidate = benchmark(lambda: None, iterations=2, warmup=0)
        comparison = compare_results(
            baseline,
            candidate,
            median_threshold=100,
            p95_threshold=100,
        )
        self.assertIsInstance(comparison.regressed, bool)

    def test_comparison_rejects_invalid_thresholds(self) -> None:
        baseline = benchmark(
            lambda: None,
            iterations=2,
            warmup=0,
            loops=1,
        )
        candidate = benchmark(
            lambda: None,
            iterations=2,
            warmup=0,
            loops=1,
        )
        for value in (-1.0, math.nan, math.inf, -math.inf, True):
            with self.subTest(median_threshold=value):
                with self.assertRaises(ValueError):
                    compare_results(
                        baseline,
                        candidate,
                        median_threshold=value,
                    )
            with self.subTest(p95_threshold=value):
                with self.assertRaises(ValueError):
                    compare_results(
                        baseline,
                        candidate,
                        p95_threshold=value,
                    )

    def test_runner_rejects_invalid_numeric_configuration(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(target_time=value):
                with self.assertRaises(ValueError):
                    benchmark(
                        lambda: None,
                        target_time=value,
                    )
            with self.subTest(min_time=value):
                with self.assertRaises(ValueError):
                    benchmark(
                        lambda: None,
                        min_time=value,
                    )

        for kwargs in (
            {"warmup": True},
            {"iterations": True},
            {"max_iterations": True},
            {"loops": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    benchmark(lambda: None, **kwargs)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux /proc required")
    def test_profile_command_native_process(self) -> None:
        profile = profile_command(
            [
                sys.executable,
                "-c",
                "import subprocess,sys;"
                "subprocess.run([sys.executable,'-c','sum(range(100000))'])",
            ],
            interval=0.001,
            check=True,
        )
        self.assertEqual(profile.returncode, 0)
        self.assertGreater(profile.wall_seconds, 0)
        self.assertGreaterEqual(profile.peak_rss_bytes, 0)
        self.assertGreaterEqual(len(profile.samples), 1)


if __name__ == "__main__":
    unittest.main()
