"""Cross-project benchmarking and profiling primitives."""

from .compare import BenchmarkComparison, compare_results
from .io import GitInfo, capture_git_info, load_result, save_result
from .perf import (\n    PerfCounter,\n    PerfStatResult,\n    perf_available,\n    perf_record,\n    perf_script,\n    perf_stat,\n)\nfrom .plot import plot_benchmark, plot_history, plot_process_samples
from .process import ProcessDetail, ProcessProfile, ProcessSample, profile_command
from .report import format_comparison, format_process_profile
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark
from .suite import BenchmarkCase, BenchmarkSuite

__all__ = [
    "BenchmarkCase",\n    "BenchmarkHistory",
    "BenchmarkComparison",
    "BenchmarkResult",
    "BenchmarkStats",
    "BenchmarkSuite",
    "GitInfo",\n    "HistoryPoint",\n    "PerfCounter",\n    "PerfStatResult",
    "ProcessDetail",
    "ProcessProfile",
    "ProcessSample",
    "SystemInfo",\n    "Trend",
    "benchmark",
    "capture_git_info",
    "compare_results",
    "format_comparison",
    "format_process_profile",
    "load_result",
    "perf_available",\n    "perf_record",\n    "perf_script",\n    "perf_stat",\n    "plot_benchmark",\n    "plot_history",
    "plot_process_samples",
    "profile_command",
    "save_process_csv",
    "save_process_html",
    "save_result",
]
