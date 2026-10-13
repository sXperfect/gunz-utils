"""Derived performance metrics shared by all measurement backends."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
from collections.abc import Sequence

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .perf import PerfStatResult
from .process import ProcessProfile


def perf_metrics(
    result: PerfStatResult,
) -> dict[str, float | None]:
    """Derive common ratios from perf-stat counters.

    Parameters
    ----------
    result : PerfStatResult
        result parameter.

    Returns
    -------
    dict[str, float | None]
        The result of the operation.
    """
    values = {counter.event: counter.value for counter in result.counters}

    def ratio(
        numerator: str,
        denominator: str,
    ) -> float | None:
        """ratio() function.

        Parameters
        ----------
        numerator : str
            numerator parameter.
        denominator : str
            denominator parameter.

        Returns
        -------
        float | None
            The result of the operation.
        """
        top, bottom = values.get(numerator), values.get(denominator)
        if top is None or bottom is None or bottom == 0:
            return None
        return top / bottom

    return {
        "ipc": ratio("instructions", "cycles"),
        "branch_miss_rate": ratio("branch-misses", "branches"),
        "cache_miss_rate": ratio("cache-misses", "cache-references"),
    }


def process_metrics(
    profile: ProcessProfile,
) -> dict[str, float | None]:
    """Derive aggregate efficiency and bandwidth metrics.

    Parameters
    ----------
    profile : ProcessProfile
        profile parameter.

    Returns
    -------
    dict[str, float | None]
        The result of the operation.
    """
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
    """Return efficiency relative to the first worker/duration observation.

    Parameters
    ----------
    workers : Sequence[int]
        workers parameter.
    durations : Sequence[float]
        durations parameter.

    Returns
    -------
    list[float | None]
        The result of the operation.
    """
    if len(workers) != len(durations) or not workers:
        raise ValueError("workers and durations must be non-empty and equally sized")
    base_workers, base_duration = workers[0], durations[0]
    if (
        isinstance(base_workers, bool)
        or not isinstance(base_workers, int)
        or base_workers <= 0
        or isinstance(base_duration, bool)
        or not isinstance(base_duration, (int, float))
    ):
        raise ValueError(
            "baseline worker count and duration must be finite and positive"
        )
    try:
        base_duration_f = float(base_duration)
    except OverflowError:
        #? A finite duration that is not float-representable (e.g. 10**400)
        #? must surface as the documented ValueError, not leak an internal
        #? OverflowError.
        raise ValueError(
            "baseline worker count and duration must be finite and positive"
        ) from None
    if not math.isfinite(base_duration_f) or base_duration <= 0:
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
        ):
            result.append(None)
            continue
        try:
            duration_f = float(duration)
        except OverflowError:
            #? An unrepresentable finite duration is a data validation error,
            #? not a skipped measurement: surface the documented ValueError.
            raise ValueError(
                "workers and durations must be finite and positive"
            ) from None
        if not math.isfinite(duration_f) or duration <= 0:
            result.append(None)
            continue
        speedup = float(base_duration) / float(duration)
        ideal_scale = count / base_workers
        result.append(speedup / ideal_scale)
    return result


__all__ = ["perf_metrics", "process_metrics", "scaling_efficiency"]
