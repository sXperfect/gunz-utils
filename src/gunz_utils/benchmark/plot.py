"""Optional plotting helpers for benchmark and profiling results."""

from __future__ import annotations

from typing import Any

from .history import BenchmarkHistory
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


def _cpu_cores(profile: ProcessProfile) -> tuple[list[float], list[float]]:
    times: list[float] = []
    values: list[float] = []
    previous = None
    for sample in profile.samples:
        if previous is not None:
            elapsed = sample.elapsed - previous.elapsed
            cpu_now = sample.cpu_user_seconds + sample.cpu_system_seconds
            cpu_before = previous.cpu_user_seconds + previous.cpu_system_seconds
            if elapsed > 0:
                times.append(sample.elapsed)
                values.append(max(0.0, (cpu_now - cpu_before) / elapsed))
        previous = sample
    return times, values


def plot_process_samples(profile: ProcessProfile, metric: str = "rss_bytes") -> Any:
    """Plot a process-tree resource metric over elapsed time."""
    allowed = {
        "rss_bytes",
        "pss_bytes",
        "private_bytes",
        "cpu_user_seconds",
        "cpu_system_seconds",
        "cpu_cores",
        "read_bytes",
        "write_bytes",
        "process_count",
        "threads",
        "minor_faults",
        "major_faults",
    }
    if metric not in allowed:
        raise ValueError(f"unsupported process metric: {metric}")
    plt = _pyplot()
    figure, axis = plt.subplots()
    if metric == "cpu_cores":
        times, values = _cpu_cores(profile)
    else:
        times = [sample.elapsed for sample in profile.samples]
        values = [getattr(sample, metric) for sample in profile.samples]
    axis.plot(times, values)
    axis.set_title(f"Process tree: {metric}")
    axis.set_xlabel("Elapsed seconds")
    axis.set_ylabel(metric)
    return figure


__all__ = ["plot_benchmark", "plot_process_samples"]
