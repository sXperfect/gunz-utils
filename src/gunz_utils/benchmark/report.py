"""Human-readable benchmark reports."""

from __future__ import annotations

from .compare import BenchmarkComparison
from .process import ProcessProfile


def format_comparison(comparison: BenchmarkComparison) -> str:
    """Format benchmark changes as a compact Markdown table."""
    rows = [
        ("Median", comparison.median_change),
        ("P95", comparison.p95_change),
        ("Mean", comparison.mean_change),
    ]
    lines = ["| Metric | Change |", "|---|---:|"]
    lines.extend(f"| {name} | {change:+.2%} |" for name, change in rows)
    lines.append("")
    lines.append(f"Regression: {'yes' if comparison.regressed else 'no'}")
    return "\n".join(lines)


def format_process_profile(profile: ProcessProfile) -> str:
    """Format key process-tree resource measurements as Markdown."""
    cpu = profile.cpu_user_seconds + profile.cpu_system_seconds
    cpu_util = 0.0 if profile.wall_seconds == 0 else cpu / profile.wall_seconds
    rows = [
        ("Wall time", f"{profile.wall_seconds:.6f} s"),
        ("CPU time", f"{cpu:.6f} s"),
        ("Average CPU cores", f"{cpu_util:.2f}"),
        ("Peak RSS", str(profile.peak_rss_bytes)),
        ("Peak processes", str(profile.peak_process_count)),
        ("Peak threads", str(profile.peak_threads)),
        ("Read bytes", str(profile.read_bytes)),
        ("Write bytes", str(profile.write_bytes)),
        ("Minor faults", str(profile.minor_faults)),
        ("Major faults", str(profile.major_faults)),
        ("Voluntary context switches", str(profile.voluntary_context_switches)),
        ("Involuntary context switches", str(profile.involuntary_context_switches)),
    ]
    lines = ["| Metric | Value |", "|---|---:|"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    return "\n".join(lines)


__all__ = ["format_comparison", "format_process_profile"]
