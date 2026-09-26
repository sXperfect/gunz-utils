"""Optional plotting helpers for benchmark and profiling results."""

from __future__ import annotations

from typing import Any

from .process import ProcessProfile
from .result import BenchmarkResult


def _pyplot() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "plotting requires matplotlib; install it in the calling project"
        ) from exc
    return plt


def plot_benchmark(result: BenchmarkResult) -> Any:
    """Plot raw benchmark iteration durations and return the figure."""
    plt = _pyplot()
    figure, axis = plt.subplots()
    axis.plot(range(1, len(result.samples) + 1), result.samples)
    axis.set_title(result.name)
    axis.set_xlabel("Iteration")
    axis.set_ylabel("Seconds")
    return figure


def plot_process_samples(profile: ProcessProfile, metric: str = "rss_bytes") -> Any:
    """Plot a process-tree resource metric over elapsed time."""
    allowed = {
        "rss_bytes",
        "cpu_user_seconds",
        "cpu_system_seconds",
        "read_bytes",
        "write_bytes",
        "process_count",
    }
    if metric not in allowed:
        raise ValueError(f"unsupported process metric: {metric}")
    plt = _pyplot()
    figure, axis = plt.subplots()
    axis.plot(
        [sample.elapsed for sample in profile.samples],
        [getattr(sample, metric) for sample in profile.samples],
    )
    axis.set_title(f"Process tree: {metric}")
    axis.set_xlabel("Elapsed seconds")
    axis.set_ylabel(metric)
    return figure


__all__ = ["plot_benchmark", "plot_process_samples"]
