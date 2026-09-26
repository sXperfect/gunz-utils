"""Cross-project benchmarking and profiling primitives."""

from .compare import BenchmarkComparison, compare_results
from .plot import plot_benchmark, plot_process_samples
from .process import ProcessProfile, ProcessSample, profile_command
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark

__all__ = [
    "BenchmarkCase",\n    "BenchmarkComparison",\n    "BenchmarkSuite",\n    "GitInfo",
    "BenchmarkResult",
    "BenchmarkStats",
    "ProcessProfile",
    "ProcessSample",
    "SystemInfo",
    "benchmark",
    "capture_git_info",\n    "compare_results",\n    "format_comparison",\n    "format_process_profile",\n    "load_result",
    "plot_benchmark",
    "plot_process_samples",
    "profile_command",\n    "save_result",
]
