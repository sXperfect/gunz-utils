"""Cross-project benchmarking and profiling primitives."""

from .compare import BenchmarkComparison, compare_results
from .plot import plot_benchmark, plot_process_samples
from .process import ProcessProfile, ProcessSample, profile_command
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark

__all__ = [
    "BenchmarkComparison",
    "BenchmarkResult",
    "BenchmarkStats",
    "ProcessProfile",
    "ProcessSample",
    "SystemInfo",
    "benchmark",
    "compare_results",
    "plot_benchmark",
    "plot_process_samples",
    "profile_command",
]
