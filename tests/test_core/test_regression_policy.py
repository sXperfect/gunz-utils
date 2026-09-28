from __future__ import annotations

import math
import unittest
from typing import Any, cast

from gunz_utils.benchmark import MetricPolicy, evaluate_metric


class TestRegressionPolicy(unittest.TestCase):
    def test_policy_validates_direction_and_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            MetricPolicy("latency", cast(Any, "sideways"))

        for value in (-0.01, math.nan, math.inf, -math.inf, True):
            with self.subTest(relative_threshold=value):
                with self.assertRaises(ValueError):
                    MetricPolicy(
                        "latency",
                        "lower",
                        relative_threshold=value,
                    )
            with self.subTest(absolute_threshold=value):
                with self.assertRaises(ValueError):
                    MetricPolicy(
                        "latency",
                        "lower",
                        absolute_threshold=value,
                    )

    def test_metric_values_must_be_finite_numbers(self) -> None:
        policy = MetricPolicy("latency", "lower")
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(baseline=value):
                with self.assertRaises(ValueError):
                    evaluate_metric(value, 1.0, policy)
            with self.subTest(candidate=value):
                with self.assertRaises(ValueError):
                    evaluate_metric(1.0, value, policy)

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
