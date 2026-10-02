#!/usr/bin/env python3
"""Downstream performance-regression harness for gunz-utils using gunz-bench.

Runs deterministic workloads, records artifacts, and checks for regressions.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from gunz_bench import (
        BenchmarkRegistry,
        BenchmarkRunner,
        compare_runs,
        load_run,
        save_run,
    )
except ImportError:
    sys.exit(
        "gunz-bench is required to execute performance regression runs.\n"
        "Install it via: pip install gunz-bench"
    )

# Add repo root and src to sys.path so workloads can import gunz_utils
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from benchmarks.workloads import get_specs  # noqa: E402


def run_benchmarks(
    *,
    baseline_path: Path | None = None,
    save_baseline_path: Path | None = None,
    output_dir: Path | None = None,
    profile: str = "regression",
    threshold: float = 0.20,
) -> int:
    specs = get_specs()
    if profile == "smoke":
        # Scale down repetitions for rapid smoke check
        scaled_specs = []
        for s in specs:
            scaled_specs.append(
                s.__class__(
                    name=s.name,
                    func=s.func,
                    repetitions=max(2, s.repetitions // 3),
                    warmup=max(1, s.warmup // 2),
                    tags=s.tags,
                )
            )
        specs = scaled_specs

    print(f"Running {len(specs)} workloads under profile '{profile}'...")
    registry = BenchmarkRegistry()
    for s in specs:
        registry.register(s)

    runner = BenchmarkRunner(registry)
    run = runner.run()

    # Save artifact
    out_dir = output_dir or (REPO_ROOT / "tmp" / "benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    artifact_path = out_dir / f"run_{timestamp}_{run.run_id[:8]}.json"
    save_run(run, artifact_path)
    print(f"Artifact saved: {artifact_path}")

    if save_baseline_path is not None:
        save_baseline_path.parent.mkdir(parents=True, exist_ok=True)
        save_run(run, save_baseline_path)
        print(f"Baseline saved: {save_baseline_path}")

    exit_code = 0
    if baseline_path is not None:
        if not baseline_path.exists():
            print(f"Baseline not found at {baseline_path}; skipping check.")
            return 0

        baseline = load_run(baseline_path)
        comparisons = compare_runs(baseline, run)
        print("\n--- Performance Regression Comparison ---")
        regressions = 0
        for comp in comparisons:
            rel = comp.relative_change
            rel_str = f"{rel:+.2%}" if rel is not None else "N/A"
            flag = " "
            if rel is not None and rel > threshold:
                flag = "!"
                regressions += 1
            b_val = comp.baseline_value
            c_val = comp.current_value
            bv = f"{b_val:.6f}" if b_val is not None else "N/A"
            cv = f"{c_val:.6f}" if c_val is not None else "N/A"
            print(f"[{flag}] {comp.name:<40} | base: {bv} | cur: {cv} | {rel_str}")

        if regressions > 0:
            print(f"\nFAILURE: {regressions} workload(s) regressed > {threshold:+.0%}")
            exit_code = 1
        else:
            print(f"\nSUCCESS: All workloads within {threshold:+.0%} threshold")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="gunz-utils performance regression runner"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline BenchmarkRun JSON",
    )
    parser.add_argument(
        "--save-baseline",
        type=Path,
        default=None,
        help="Save current run as baseline",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save run artifacts",
    )
    parser.add_argument(
        "--profile",
        choices=["smoke", "regression"],
        default="smoke",
        help="Execution profile",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        help="Regression threshold (default: 0.20 = +20%)",
    )
    args = parser.parse_args()

    return run_benchmarks(
        baseline_path=args.baseline,
        save_baseline_path=args.save_baseline,
        output_dir=args.output_dir,
        profile=args.profile,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    sys.exit(main())
