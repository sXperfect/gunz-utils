from __future__ import annotations

import unittest

from gunz_utils.benchmark import MetricPolicy, evaluate_metric


class TestRegressionPolicy(unittest.TestCase):
    def test_lower_is_better(self) -> None:
        policy = MetricPolicy("latency", "lower", relative_threshold=0.05)
        self.assertTrue(evaluate_metric(1.0, 1.04, policy).passed)
        self.assertFalse(evaluate_metric(1.0, 1.10, policy).passed)

    def test_higher_is_better(self) -> None:
        policy = MetricPolicy("throughput", "higher", relative_threshold=0.05)
        self.assertTrue(evaluate_metric(100.0, 110.0, policy).passed)
        self.assertFalse(evaluate_metric(100.0, 90.0, policy).passed)


if __name__ == "__main__":
    unittest.main()
