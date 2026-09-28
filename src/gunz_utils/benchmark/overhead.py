"""Self-overhead probes for benchmark/profiling infrastructure."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .runner import benchmark


@dataclass(frozen=True)
class OverheadProbe:
    benchmark_call_seconds: float
    timer_pair_seconds: float
    ratio: float


def measure_runner_overhead(*, iterations: int = 20) -> OverheadProbe:
    """Estimate framework overhead using a no-op benchmark."""
    if (
        isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or iterations < 1
    ):
        raise ValueError("iterations must be a positive integer")
    timer_samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        time.perf_counter()
        timer_samples.append(time.perf_counter() - started)
    timer = sum(timer_samples) / len(timer_samples)
    result = benchmark(
        lambda: None,
        warmup=0,
        iterations=iterations,
        loops=1,
        disable_gc=False,
    )
    measured = result.stats.mean
    ratio = float("inf") if timer == 0 else measured / timer
    return OverheadProbe(measured, timer, ratio)


__all__ = ["OverheadProbe", "measure_runner_overhead"]
