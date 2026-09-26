"""Cross-project benchmarking and profiling primitives."""

from .compare import BenchmarkComparison, compare_results
from .plot import plot_benchmark, plot_process_samples
from .process import ProcessProfile, ProcessSample, profile_command
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark

__all__ = [
    "BenchmarkCase",
    "BenchmarkComparison",
    "BenchmarkSuite",
    "GitInfo",
    "BenchmarkResult",
    "BenchmarkStats",
    "ProcessProfile",
    "ProcessSample",
    "SystemInfo",
    "benchmark",
    "capture_git_info",
    "compare_results",
    "format_comparison",
    "format_process_profile",
    "load_result",
    "plot_benchmark",
    "plot_process_samples",
    "profile_command",
    "save_result",
]
