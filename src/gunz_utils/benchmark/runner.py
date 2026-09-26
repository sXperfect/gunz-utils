"""Repeatable microbenchmark runner."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from typing import Any, TypeVar

from .result import BenchmarkResult, BenchmarkStats, SystemInfo

T = TypeVar("T")


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def benchmark(
    func: Callable[..., T],
    *args: Any,
    name: str | None = None,
    warmup: int = 3,
    iterations: int = 20,
    parameters: dict[str, Any] | None = None,
    **kwargs: Any,
) -> BenchmarkResult:
    """Benchmark a callable using warmup and monotonic wall-clock samples."""
    if warmup < 0 or iterations < 1:
        raise ValueError("warmup must be non-negative and iterations positive")
    for _ in range(warmup):
        func(*args, **kwargs)

    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        func(*args, **kwargs)
        samples.append(time.perf_counter() - started)

    mean = statistics.fmean(samples)
    stats = BenchmarkStats(
        minimum=min(samples),
        median=statistics.median(samples),
        mean=mean,
        p95=_percentile(samples, 0.95),
        p99=_percentile(samples, 0.99),
        maximum=max(samples),
        stddev=statistics.pstdev(samples),
        ops_per_second=float("inf") if mean == 0 else 1.0 / mean,
    )
    return BenchmarkResult(
        name=name or getattr(func, "__qualname__", repr(func)),
        samples=tuple(samples),
        stats=stats,
        warmup=warmup,
        iterations=iterations,
        system=SystemInfo.capture(),
        parameters={} if parameters is None else dict(parameters),
    )


__all__ = ["benchmark"]
