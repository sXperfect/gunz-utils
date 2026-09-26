"""Build normalized PerformanceRun values from collected measurements."""

from __future__ import annotations

from dataclasses import replace

from .diagnostics import analyze_stability
from .environment import capture_noise_info
from .io import capture_git_info
from .metrics import process_metrics
from .performance import PerformanceRun
from .process import ProcessProfile
from .result import BenchmarkResult


def build_performance_run(
    name: str,
    *,
    benchmark: BenchmarkResult | None = None,
    process_profile: ProcessProfile | None = None,
    cwd: str | None = None,
) -> PerformanceRun:
    """Assemble provenance, derived metrics and warnings automatically."""
    if benchmark is None and process_profile is None:
        raise ValueError("at least one measurement is required")
    system = benchmark.system if benchmark is not None else None
    if system is None:
        from .result import SystemInfo
        system = SystemInfo.capture()
    metrics: dict[str, float | int | None] = {}
    warnings: list[str] = []
    if process_profile is not None:
        metrics.update(process_metrics(process_profile))
    if benchmark is not None:
        stability = analyze_stability(benchmark)
        warnings.extend(stability.warnings)
        metrics["benchmark_cv"] = stability.coefficient_of_variation
    noise = capture_noise_info()
    if noise.load_1m is not None and system.cpu_count:
        if noise.load_1m > system.cpu_count:
            warnings.append("system load exceeds logical CPU count")
    return PerformanceRun(
        name=name,
        system=system,
        git=capture_git_info(cwd),
        benchmark=benchmark,
        process_profile=process_profile,
        metrics=metrics,
        warnings=tuple(warnings),
    )


__all__ = ["build_performance_run"]
