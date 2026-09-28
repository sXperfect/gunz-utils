from __future__ import annotations

import unittest

from gunz_utils.benchmark import (
    BenchmarkHistory,
    benchmark,
    perf_available,
    summarize_history,
)


class TestBenchmarkHistory(unittest.TestCase):
    def test_trend(self) -> None:
        first = benchmark(lambda: None, warmup=0, iterations=2)
        second = benchmark(lambda: None, warmup=0, iterations=2)
        history = BenchmarkHistory().add("a", first).add("b", second)
        trend = history.trend("median")
        self.assertEqual(trend.metric, "median")
        self.assertEqual(len(history.points), 2)

    def test_empty_history_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkHistory().trend()

    def test_unknown_metric_is_rejected_explicitly(self) -> None:
        result = benchmark(
            lambda: None,
            warmup=0,
            iterations=2,
            loops=1,
        )
        history = BenchmarkHistory().add("a", result)
        with self.assertRaisesRegex(ValueError, "unknown benchmark metric"):
            history.trend("not_a_metric")
        with self.assertRaisesRegex(ValueError, "unknown benchmark metric"):
            summarize_history(history, metric="not_a_metric")

    def test_summary_validates_baseline_window(self) -> None:
        result = benchmark(
            lambda: None,
            warmup=0,
            iterations=2,
            loops=1,
        )
        history = BenchmarkHistory().add("a", result)
        with self.assertRaises(ValueError):
            summarize_history(history, baseline_window=True)

    def test_perf_detection_is_boolean(self) -> None:
        self.assertIsInstance(perf_available(), bool)


if __name__ == "__main__":
    unittest.main()
