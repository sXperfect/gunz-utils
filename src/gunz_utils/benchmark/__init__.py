"""Cross-project benchmarking and profiling primitives."""

from .compare import BenchmarkComparison, compare_results
from .io import GitInfo, capture_git_info, load_result, save_result
from .plot import plot_benchmark, plot_process_samples
from .process import ProcessDetail, ProcessProfile, ProcessSample, profile_command
from .report import format_comparison, format_process_profile
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark
from .suite import BenchmarkCase, BenchmarkSuite

__all__ = [
    "BenchmarkCase",
    "BenchmarkComparison",
    "BenchmarkResult",
    "BenchmarkStats",
    "BenchmarkSuite",
    "GitInfo",
    "ProcessDetail",\n    "ProcessProfile",
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
    "save_process_csv",\n    "save_process_html",\n    "save_result",
]
