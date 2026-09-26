"""Repeatable microbenchmark runner with native calibration."""

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


def calibrate_loops(
    func: Callable[..., T],
    *args: Any,
    target_time: float = 0.05,
    max_loops: int = 1 << 30,
    **kwargs: Any,
) -> int:
    """Choose a loop count that makes one timing sample sufficiently long."""
    if target_time <= 0:
        raise ValueError("target_time must be positive")
    loops = 1
    while True:
        started = time.perf_counter()
        for _ in range(loops):
            func(*args, **kwargs)
        elapsed = time.perf_counter() - started
        if elapsed >= target_time or loops >= max_loops:
            return loops
        if elapsed <= 0:
            loops = min(max_loops, loops * 10)
        else:
            scale = max(2, min(10, int(target_time / elapsed)))
            loops = min(max_loops, loops * scale)


def _sample(
    func: Callable[..., T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    loops: int,
) -> float:
    started = time.perf_counter()
    for _ in range(loops):
        func(*args, **kwargs)
    return (time.perf_counter() - started) / loops


def benchmark(
    func: Callable[..., T],
    *args: Any,
    name: str | None = None,
    warmup: int = 3,
    iterations: int = 20,
    parameters: dict[str, Any] | None = None,
    loops: int | None = None,
    target_time: float = 0.05,
    **kwargs: Any,
) -> BenchmarkResult:
    """Benchmark a callable with calibrated loops and per-operation samples."""
    if warmup < 0 or iterations < 1:
        raise ValueError("warmup must be non-negative and iterations positive")
    if loops is not None and loops < 1:
        raise ValueError("loops must be positive")
    actual_loops = loops or calibrate_loops(
        func,
        *args,
        target_time=target_time,
        **kwargs,
    )
    for _ in range(warmup):
        _sample(func, args, kwargs, actual_loops)

    samples = [
        _sample(func, args, kwargs, actual_loops)
        for _ in range(iterations)
    ]
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
    result_parameters = {} if parameters is None else dict(parameters)
    result_parameters.setdefault("_loops", actual_loops)
    return BenchmarkResult(
        name=name or getattr(func, "__qualname__", repr(func)),
        samples=tuple(samples),
        stats=stats,
        warmup=warmup,
        iterations=iterations,
        system=SystemInfo.capture(),
        parameters=result_parameters,
    )


__all__ = ["benchmark", "calibrate_loops"]
