"""Derived performance metrics shared by all measurement backends."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .perf import PerfStatResult
from .process import ProcessProfile


def perf_metrics(result: PerfStatResult) -> dict[str, float | None]:
    """Derive common ratios from perf-stat counters."""
    values = {counter.event: counter.value for counter in result.counters}

    def ratio(numerator: str, denominator: str) -> float | None:
        top, bottom = values.get(numerator), values.get(denominator)
        if top is None or bottom is None or bottom == 0:
            return None
        return top / bottom

    return {
        "ipc": ratio("instructions", "cycles"),
        "branch_miss_rate": ratio("branch-misses", "branches"),
        "cache_miss_rate": ratio("cache-misses", "cache-references"),
    }


def process_metrics(profile: ProcessProfile) -> dict[str, float | None]:
    """Derive aggregate efficiency and bandwidth metrics."""
    wall = profile.wall_seconds
    samples = profile.samples
    memory_time = 0.0
    for previous, current in zip(samples, samples[1:], strict=False):
        duration = current.elapsed - previous.elapsed
        memory_time += previous.rss_bytes * max(0.0, duration)
    return {
        "average_cpu_cores": profile.average_cpu_cores,
        "read_bytes_per_second": None if wall == 0 else profile.read_bytes / wall,
        "write_bytes_per_second": None if wall == 0 else profile.write_bytes / wall,
        "rss_byte_seconds": memory_time,
        "peak_pss_rss_ratio": (
            None
            if not profile.peak_rss_bytes or profile.peak_pss_bytes is None
            else profile.peak_pss_bytes / profile.peak_rss_bytes
        ),
    }


def scaling_efficiency(
    workers: Sequence[int],
    durations: Sequence[float],
) -> list[float | None]:
    """Return efficiency relative to the first worker/duration observation."""
    if len(workers) != len(durations) or not workers:
        raise ValueError("workers and durations must be non-empty and equally sized")
    base_workers, base_duration = workers[0], durations[0]
    if (
        isinstance(base_workers, bool)
        or not isinstance(base_workers, int)
        or base_workers <= 0
        or isinstance(base_duration, bool)
        or not isinstance(base_duration, (int, float))
        or not math.isfinite(float(base_duration))
        or base_duration <= 0
    ):
        raise ValueError(
            "baseline worker count and duration must be finite and positive"
        )

    result: list[float | None] = []
    for count, duration in zip(workers, durations, strict=True):
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            or isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(float(duration))
            or duration <= 0
        ):
            result.append(None)
            continue
        speedup = float(base_duration) / float(duration)
        ideal_scale = count / base_workers
        result.append(speedup / ideal_scale)
    return result


__all__ = ["perf_metrics", "process_metrics", "scaling_efficiency"]
