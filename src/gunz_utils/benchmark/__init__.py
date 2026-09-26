"""Cross-project benchmarking and profiling primitives."""

from .compare import BenchmarkComparison, compare_results
from .export import save_process_csv, save_process_html
from .history import BenchmarkHistory, HistoryPoint, Trend
from .io import GitInfo, capture_git_info, load_result, save_result
from .performance import PerformanceArtifact, PerformanceRun
from .perf import (
    PerfCounter,
    PerfStatResult,
    perf_available,
    perf_record,
    perf_script,
    perf_stat,
)
from .plot import plot_benchmark, plot_history, plot_process_samples
from .process import ProcessDetail, ProcessProfile, ProcessSample, profile_command
from .report import format_comparison, format_process_profile
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark, benchmark_environment, calibrate_loops
from .suite import BenchmarkCase, BenchmarkSuite
from .worker import WorkerResult, run_python_worker, worker_json

__all__ = [
    "BenchmarkCase",
    "BenchmarkComparison",
    "BenchmarkHistory",
    "BenchmarkResult",
    "BenchmarkStats",
    "BenchmarkSuite",
    "GitInfo",
    "HistoryPoint",
    "PerformanceArtifact",
    "PerformanceRun",
    "PerfCounter",
    "PerfStatResult",
    "ProcessDetail",
    "ProcessProfile",
    "ProcessSample",
    "StabilityReport",
    "SystemInfo",
    "Trend",
    "WorkerResult",
    "analyze_stability",
    "benchmark",
    "benchmark_environment",
    "calibrate_loops",
    "comparability_warnings",
    "capture_git_info",
    "compare_results",
    "format_comparison",
    "format_process_profile",
    "load_result",
    "perf_available",
    "perf_record",
    "perf_script",
    "perf_stat",
    "plot_benchmark",
    "plot_history",
    "plot_process_samples",
    "profile_command",
    "save_process_csv",
    "save_process_html",
    "run_python_worker",
    "save_result",
    "worker_json",
]
