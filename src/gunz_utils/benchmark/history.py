"""Benchmark history and trend analysis across revisions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .io import load_result
from .result import BenchmarkResult


@dataclass(frozen=True)
class HistoryPoint:
    """One ordered benchmark observation."""

    label: str
    result: BenchmarkResult


@dataclass(frozen=True)
class Trend:
    """Summary change across an ordered benchmark history."""

    metric: str
    first: float
    last: float
    absolute_change: float
    relative_change: float
    best: float
    worst: float


class BenchmarkHistory:
    """Ordered benchmark results, typically one per commit or release."""

    def __init__(self, points: Iterable[HistoryPoint] = ()) -> None:
        self.points = list(points)

    def add(self, label: str, result: BenchmarkResult) -> BenchmarkHistory:
        self.points.append(HistoryPoint(label, result))
        return self

    @classmethod
    def from_files(cls, paths: Iterable[str | Path]) -> BenchmarkHistory:
        history = cls()
        for path in paths:
            item = Path(path)
            history.add(item.stem, load_result(item))
        return history

    def trend(self, metric: str = "median") -> Trend:
        if not self.points:
            raise ValueError("benchmark history is empty")
        values = [float(getattr(point.result.stats, metric)) for point in self.points]
        first, last = values[0], values[-1]
        absolute = last - first
        relative = 0.0 if first == 0 and last == 0 else (
            float("inf") if first == 0 else absolute / first
        )
        return Trend(
            metric=metric,
            first=first,
            last=last,
            absolute_change=absolute,
            relative_change=relative,
            best=min(values),
            worst=max(values),
        )


__all__ = ["BenchmarkHistory", "HistoryPoint", "Trend"]
