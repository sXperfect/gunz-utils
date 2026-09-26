from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gunz_utils.benchmark import (
    BenchmarkSuite,
    benchmark,
    capture_git_info,
    format_comparison,
    load_result,
    save_result,
)
from gunz_utils.benchmark.compare import compare_results


class TestBenchmarkReporting(unittest.TestCase):
    def test_result_round_trip(self) -> None:
        result = benchmark(lambda: sum(range(5)), warmup=0, iterations=2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            save_result(result, path)
            loaded = load_result(path)
        self.assertEqual(loaded.name, result.name)
        self.assertEqual(loaded.samples, result.samples)

    def test_suite(self) -> None:
        suite = BenchmarkSuite("demo")
        suite.add("sum", sum, range(10))
        results = suite.run(warmup=0, iterations=2)
        self.assertEqual(results[0].name, "demo.sum")

    def test_comparison_report(self) -> None:
        baseline = benchmark(lambda: None, warmup=0, iterations=2)
        candidate = benchmark(lambda: None, warmup=0, iterations=2)
        report = format_comparison(
            compare_results(
                baseline,
                candidate,
                median_threshold=100,
                p95_threshold=100,
            )
        )
        self.assertIn("| Metric | Change |", report)

    def test_git_capture_is_non_throwing(self) -> None:
        info = capture_git_info()
        self.assertTrue(info.commit is None or isinstance(info.commit, str))


if __name__ == "__main__":
    unittest.main()
