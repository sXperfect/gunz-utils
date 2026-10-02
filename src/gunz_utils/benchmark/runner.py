"""Repeatable microbenchmark runner with native calibration and controls."""

from __future__ import annotations

import gc
import math
import os
import statistics
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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


@contextmanager
def benchmark_environment(
    *,
    disable_gc: bool = True,
    cpu_affinity: set[int] | None = None,
) -> Iterator[None]:
    """Temporarily control GC and CPU affinity for benchmark execution."""
    gc_enabled = gc.isenabled()
    previous_affinity = None
    try:
        if disable_gc and gc_enabled:
            gc.disable()
        if cpu_affinity is not None:
            sched_get = getattr(os, "sched_getaffinity", None)
            sched_set = getattr(os, "sched_setaffinity", None)
            if sched_get is None or sched_set is None:
                raise NotImplementedError(
                    "CPU affinity is unavailable on this platform"
                )
            previous_affinity = sched_get(0)
            sched_set(0, cpu_affinity)
        yield
    finally:
        if previous_affinity is not None:
            sched_set = getattr(os, "sched_setaffinity", None)
            if sched_set is not None:
                sched_set(0, previous_affinity)
        if disable_gc and gc_enabled:
            gc.enable()


def calibrate_loops(
    func: Callable[..., T],
    *args: Any,
    target_time: float = 0.05,
    max_loops: int = 1 << 30,
    **kwargs: Any,
) -> int:
    if (
        isinstance(target_time, bool)
        or not isinstance(target_time, (int, float))
        or not math.isfinite(float(target_time))
        or target_time <= 0
    ):
        raise ValueError("target_time must be a finite positive number")
    if (
        isinstance(max_loops, bool)
        or not isinstance(max_loops, int)
        or max_loops < 1
    ):
        raise ValueError("max_loops must be a positive integer")
    loops = 1
    while True:
        started = time.perf_counter()
        for _ in range(loops):
            func(*args, **kwargs)
        elapsed = time.perf_counter() - started
        if elapsed >= target_time or loops >= max_loops:
            return loops
        scale = 10 if elapsed <= 0 else max(2, min(10, int(target_time / elapsed)))
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
    min_time: float | None = None,
    max_iterations: int = 1000,
    parameters: dict[str, Any] | None = None,
    loops: int | None = None,
    target_time: float = 0.05,
    disable_gc: bool = True,
    cpu_affinity: set[int] | None = None,
    **kwargs: Any,
) -> BenchmarkResult:
    """Benchmark a callable with calibration and controlled execution."""
    if (
        isinstance(warmup, bool)
        or not isinstance(warmup, int)
        or warmup < 0
        or isinstance(iterations, bool)
        or not isinstance(iterations, int)
        or iterations < 1
        or isinstance(max_iterations, bool)
        or not isinstance(max_iterations, int)
        or max_iterations < iterations
    ):
        raise ValueError("invalid warmup/iteration configuration")
    if min_time is not None and (
        isinstance(min_time, bool)
        or not isinstance(min_time, (int, float))
        or not math.isfinite(float(min_time))
        or min_time < 0
    ):
        raise ValueError(
            "min_time must be a finite non-negative number or None"
        )
    if loops is not None and (
        isinstance(loops, bool)
        or not isinstance(loops, int)
        or loops < 1
    ):
        raise ValueError("loops must be a positive integer or None")
    if (
        isinstance(target_time, bool)
        or not isinstance(target_time, (int, float))
        or not math.isfinite(float(target_time))
        or target_time <= 0
    ):
        raise ValueError("target_time must be a finite positive number")

    with benchmark_environment(
        disable_gc=disable_gc,
        cpu_affinity=cpu_affinity,
    ):
        actual_loops = loops or calibrate_loops(
            func,
            *args,
            target_time=target_time,
            **kwargs,
        )
        for _ in range(warmup):
            _sample(func, args, kwargs, actual_loops)

        samples: list[float] = []
        measured = 0.0
        while len(samples) < max_iterations:
            sample = _sample(func, args, kwargs, actual_loops)
            samples.append(sample)
            measured += sample * actual_loops
            enough_count = len(samples) >= iterations
            enough_time = min_time is None or measured >= min_time
            if enough_count and enough_time:
                break

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
    result_parameters.update(
        {
            "_loops": actual_loops,
            "_gc_disabled": disable_gc,
            "_cpu_affinity": sorted(cpu_affinity) if cpu_affinity else None,
        }
    )
    return BenchmarkResult(
        name=name or str(getattr(func, "__qualname__", repr(func))),
        samples=tuple(samples),
        stats=stats,
        warmup=warmup,
        iterations=len(samples),
        system=SystemInfo.capture(),
        parameters=result_parameters,
    )


__all__ = ["benchmark", "benchmark_environment", "calibrate_loops"]
