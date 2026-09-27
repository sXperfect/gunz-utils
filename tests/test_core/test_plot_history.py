"""Regression coverage for the public, optional history plotting helper."""

import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from gunz_utils.benchmark import BenchmarkHistory, benchmark, plot_history


class TestPlotHistory(unittest.TestCase):
    """Keep history plotting importable without installing matplotlib."""

    def setUp(self) -> None:
        """Build deterministic statistics without depending on timer values."""
        result = benchmark(lambda: None, warmup=0, iterations=2)
        first = replace(result, stats=replace(result.stats, median=1.0, mean=2.0))
        second = replace(result, stats=replace(result.stats, median=3.0, mean=4.0))
        self.history = BenchmarkHistory().add("release", first).add("release", second)

    def test_plot_preserves_order_and_duplicate_labels(self) -> None:
        """Repeated release labels should still occupy distinct positions."""
        for metric, values in (("median", [1.0, 3.0]), ("mean", [2.0, 4.0])):
            with self.subTest(metric=metric):
                pyplot = Mock()
                figure, axis = Mock(), Mock()
                pyplot.subplots.return_value = (figure, axis)
                with patch("gunz_utils.benchmark.plot._pyplot", return_value=pyplot):
                    actual = (
                        plot_history(self.history)
                        if metric == "median"
                        else plot_history(self.history, metric)
                    )
                self.assertIs(actual, figure)
                axis.plot.assert_called_once_with([0, 1], values)
                axis.set_xticks.assert_called_once_with([0, 1], ["release", "release"])
                axis.set_ylabel.assert_called_once_with(metric)

    def test_empty_history_rejected_before_loading_backend(self) -> None:
        """Reject missing data even when matplotlib is unavailable."""
        with patch("gunz_utils.benchmark.plot._pyplot") as backend:
            with self.assertRaisesRegex(ValueError, "history is empty"):
                plot_history(BenchmarkHistory())
            backend.assert_not_called()

    def test_unknown_metric_rejected_before_loading_backend(self) -> None:
        """Keep invalid metric behavior consistent with history trends."""
        with patch("gunz_utils.benchmark.plot._pyplot") as backend:
            with self.assertRaises(AttributeError):
                plot_history(self.history, "unknown_metric")
            backend.assert_not_called()

    def test_missing_optional_backend_explains_requirement(self) -> None:
        """The package must import successfully when plotting is unavailable."""
        with patch.dict("sys.modules", {"matplotlib.pyplot": None}):
            with self.assertRaisesRegex(RuntimeError, "plotting requires matplotlib"):
                plot_history(self.history)
