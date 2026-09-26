"""Cross-project benchmarking and profiling primitives."""

from .artifacts import register_artifact, verify_artifact
from .backends import (
    LinuxProcSampler,
    PortableSampler,
    ProcessSampler,
    SamplerCapabilities,
    default_sampler,
)
from .compare import BenchmarkComparison, compare_results
from .diagnostics import (
    StabilityReport,
    analyze_stability,
    comparability_warnings,
)
from .environment import NoiseInfo, capture_noise_info
from .export import save_process_csv, save_process_html
from .history import BenchmarkHistory, HistoryPoint, Trend
from .io import GitInfo, capture_git_info, load_result, save_result
from .metrics import perf_metrics, process_metrics, scaling_efficiency
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
from .policy import MetricDecision, MetricPolicy, evaluate_metric
from .process import ProcessDetail, ProcessProfile, ProcessSample, profile_command
from .protocol import WORKER_PROTOCOL_VERSION, WorkerRequest, WorkerResponse
from .report import format_comparison, format_process_profile
from .result import BenchmarkResult, BenchmarkStats, SystemInfo
from .runner import benchmark, benchmark_environment, calibrate_loops
from .suite import BenchmarkCase, BenchmarkSuite
from .trends import HistorySummary, summarize_history
from .worker import WorkerResult, run_python_worker, worker_json

__all__ = [
    "BenchmarkCase", "BenchmarkComparison", "BenchmarkHistory",
    "BenchmarkResult", "BenchmarkStats", "BenchmarkSuite", "GitInfo",
    "HistoryPoint", "HistorySummary", "LinuxProcSampler", "MetricDecision",
    "MetricPolicy", "NoiseInfo", "PerformanceArtifact", "PerformanceRun",
    "PerfCounter", "PerfStatResult", "PortableSampler", "ProcessDetail",
    "ProcessProfile", "ProcessSample", "ProcessSampler", "RegressionGate",
    "SamplerCapabilities",
    "StabilityReport", "SystemInfo", "Trend", "WORKER_PROTOCOL_VERSION",
    "WorkerRequest", "WorkerResponse", "WorkerResult", "analyze_stability",
    "benchmark", "benchmark_environment", "calibrate_loops",
    "capture_git_info", "capture_noise_info", "comparability_warnings",
    "compare_results", "default_sampler", "evaluate_metric",
    "evaluate_regression_gate", "format_comparison", "format_process_profile",
    "load_result", "migrate_performance_run",
    "perf_available", "perf_metrics", "perf_record", "perf_script",
    "perf_stat", "plot_benchmark", "plot_history", "plot_process_samples",
    "process_metrics", "profile_command", "register_artifact",
    "run_python_worker", "save_process_csv", "save_process_html",
    "save_result", "scaling_efficiency", "summarize_history",
    "validate_performance_run", "verify_artifact", "worker_json",
]
