#!/usr/bin/env python3
"""Aggregate repository verification without hiding independent failures."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CI_SCRIPT = PROJECT_ROOT / "scripts" / "ci.py"
SRC_DIR = PROJECT_ROOT / "src"
DEFAULT_GATES = ("release", "lint", "test", "docs", "packaging")


@dataclass(frozen=True)
class GateResult:
    """One verification gate result."""

    name: str
    returncode: int


GateRunner = Callable[[str], int]
CompatRunner = Callable[[str], int]


def _run(
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> int:
    """Run one command from the repository root and return its status."""
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        env=env,
    )
    return result.returncode


def run_gate(name: str) -> int:
    """Run one canonical gate through scripts/ci.py."""
    return _run((sys.executable, str(CI_SCRIPT), name))


def run_compatibility(python_executable: str) -> int:
    """Run the full suite with a second Python interpreter."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR)
    return _run(
        (python_executable, "-m", "pytest"),
        env=env,
    )


def collect_results(
    *,
    gates: Sequence[str] = DEFAULT_GATES,
    gate_runner: GateRunner = run_gate,
    compatibility_python: str | None = None,
    compatibility_runner: CompatRunner = run_compatibility,
    fail_fast: bool = False,
) -> list[GateResult]:
    """Run gates and collect every result unless fail_fast is requested."""
    results: list[GateResult] = []

    for name in gates:
        print()
        print("=" * 72)
        print(f"  audit gate: {name}")
        print("=" * 72)
        try:
            returncode = int(gate_runner(name))
        except Exception as exc:
            print(
                f"!! audit gate {name} raised {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            returncode = 70
        results.append(GateResult(name, returncode))
        if returncode != 0 and fail_fast:
            return results

    if compatibility_python is not None:
        name = "python-compatibility"
        print()
        print("=" * 72)
        print(f"  audit gate: {name} ({compatibility_python})")
        print("=" * 72)
        try:
            returncode = int(compatibility_runner(compatibility_python))
        except Exception as exc:
            print(
                f"!! audit gate {name} raised {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            returncode = 70
        results.append(GateResult(name, returncode))

    return results


def _summary_payload(results: Sequence[GateResult]) -> dict[str, object]:
    """Return the stable machine-readable result document."""
    return {
        "schema_version": 1,
        "passed": all(item.returncode == 0 for item in results),
        "results": [
            {"name": item.name, "returncode": item.returncode}
            for item in results
        ],
    }


def write_json_summary(
    path: Path,
    results: Sequence[GateResult],
) -> None:
    """Write the aggregate JSON summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_summary_payload(results), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_github_summary(results: Sequence[GateResult]) -> None:
    """Append a compact table to GitHub's step summary when available."""
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return

    lines = [
        "## Repository verification",
        "",
        "| Gate | Result | Exit code |",
        "|---|---|---:|",
    ]
    for item in results:
        status = "PASS" if item.returncode == 0 else "FAIL"
        lines.append(f"| {item.name} | {status} | {item.returncode} |")
    lines.append("")

    with Path(target).open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines))


def print_summary(results: Sequence[GateResult]) -> None:
    """Print all gate statuses after execution."""
    print()
    print("=" * 72)
    print("  aggregate verification summary")
    print("=" * 72)
    for item in results:
        status = "PASS" if item.returncode == 0 else "FAIL"
        print(f"{status:4}  {item.name:24}  exit={item.returncode}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run independent repository verification gates, collect their "
            "statuses, and fail only after the summary is available."
        )
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        help="write a machine-readable aggregate result file",
    )
    parser.add_argument(
        "--compat-python",
        help="run the full pytest suite with this additional interpreter",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="stop after the first failing primary gate",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the aggregate verifier."""
    args = build_parser().parse_args(argv)
    results = collect_results(
        compatibility_python=args.compat_python,
        fail_fast=args.fail_fast,
    )
    print_summary(results)

    if args.summary_json is not None:
        write_json_summary(args.summary_json, results)
    write_github_summary(results)

    return 0 if all(item.returncode == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
