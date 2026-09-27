"""History analysis beyond pairwise benchmark comparison."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .history import BenchmarkHistory


@dataclass(frozen=True)
class HistorySummary:
    metric: str
    slope_per_step: float
    moving_baseline: float
    latest: float
    latest_change: float


def summarize_history(
    history: BenchmarkHistory,
    *,
    metric: str = "median",
    baseline_window: int = 5,
) -> HistorySummary:
    """Summarize trend slope and latest change from a moving baseline."""
    if baseline_window < 1:
        raise ValueError("baseline_window must be positive")
    values = [float(getattr(point.result.stats, metric)) for point in history.points]
    if not values:
        raise ValueError("benchmark history is empty")
    if len(values) == 1:
        slope = 0.0
    else:
        xs = list(range(len(values)))
        x_mean = statistics.fmean(xs)
        y_mean = statistics.fmean(values)
        numerator = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(xs, values, strict=True)
        )
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = 0.0 if denominator == 0 else numerator / denominator
    previous = values[max(0, len(values) - baseline_window - 1):-1]
    baseline = statistics.median(previous) if previous else values[0]
    latest = values[-1]
    change = 0.0 if baseline == latest else (
        float("inf") if baseline == 0 else (latest - baseline) / baseline
    )
    return HistorySummary(metric, slope, baseline, latest, change)


__all__ = ["HistorySummary", "summarize_history"]
