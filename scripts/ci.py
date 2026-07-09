#!/usr/bin/env python3
"""Local CI runner that mirrors ``.github/workflows/ci.yml`` matrix jobs.

Each subcommand corresponds to one matrix job and performs the same
install + ``unittest discover`` (or ruff lint) step the CI workflow runs.
Use from the project root before pushing or committing to catch failures
locally.

Examples:

    python scripts/ci.py core
    python scripts/ci.py validation-extras
    python scripts/ci.py project-extras
    python scripts/ci.py observability-extras
    python scripts/ci.py stdlib-fallback
    python scripts/ci.py secure-extras
    python scripts/ci.py ruff
    python scripts/ci.py all          # every job sequentially
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT_ROOT / "pyproject.toml"

JOB_CORE = {
    "key": "core",
    "label": "core (enums + security + upstream_protocol)",
    "install": ["pip", "install", "."],
    "tests": ["tests/test_core"],
}
JOB_VALIDATION = {
    "key": "validation-extras",
    "label": "validation (type_checked + leak)",
    "install": ["pip", "install", ".[validation]"],
    "tests": ["tests/test_validation"],
}
JOB_PROJECT = {
    "key": "project-extras",
    "label": "project (resolve_project_root)",
    "install": ["pip", "install", ".[project]"],
    "tests": ["tests/test_project"],
}
JOB_OBSERVABILITY = {
    "key": "observability-extras",
    "label": "observability (setup_logging)",
    "install": ["pip", "install", ".[observability]"],
    "tests": ["tests/test_observability"],
}
JOB_STDLIB_FALLBACK = {
    "key": "stdlib-fallback",
    "label": "stdlib fallback (validation_stdlib + project_stdlib)",
    "install": ["pip", "install", "."],
    "tests": ["tests/test_ext_stdlib"],
}
JOB_SECURE = {
    "key": "secure-extras",
    "label": "secure (SecureStore + cryptography)",
    "install": ["pip", "install", ".[secure]"],
    "tests": ["tests/test_secure"],
}

JOBS: Sequence[dict] = (
    JOB_CORE,
    JOB_VALIDATION,
    JOB_PROJECT,
    JOB_OBSERVABILITY,
    JOB_STDLIB_FALLBACK,
    JOB_SECURE,
)

RUFF_INSTALL = ["pip", "install", "ruff"]


def _run(cmd: Sequence[str]) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"!! command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def _pip_install(install_args: Sequence[str]) -> None:
    _run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    _run([sys.executable, "-m", *install_args])


def _run_unittest(test_dirs: Iterable[str]) -> None:
    for test_dir in test_dirs:
        path = PROJECT_ROOT / test_dir
        if not path.is_dir():
            print(f"!! missing test directory: {test_dir}", file=sys.stderr)
            sys.exit(2)
        _run([sys.executable, "-m", "unittest", "discover", test_dir, "-v"])


def run_job(job: dict) -> None:
    print()
    print("=" * 72)
    print(f"  job: {job['key']}  --  {job['label']}")
    print("=" * 72)
    _pip_install(job["install"])
    if job["tests"]:
        _run_unittest(job["tests"])


def run_ruff() -> None:
    print()
    print("=" * 72)
    print("  job: ruff  --  ruff lint")
    print("=" * 72)
    _pip_install(RUFF_INSTALL)
    _run([sys.executable, "-m", "ruff", "check", "src", "tests"])


def run_all() -> None:
    for job in JOBS:
        run_job(job)
    run_ruff()


def build_parser() -> argparse.ArgumentParser:
    if not PYPROJECT.is_file():
        print(f"pyproject.toml not found at {PYPROJECT}", file=sys.stderr)
        sys.exit(2)
    parser = argparse.ArgumentParser(
        prog="scripts/ci.py",
        description=(
            "Local CI runner that mirrors .github/workflows/ci.yml. "
            "Use before pushing or committing to catch failures early."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for job in JOBS:
        subparsers.add_parser(job["key"], help=f"Run the {job['label']} matrix job")
    subparsers.add_parser("ruff", help="Run the ruff lint job")
    subparsers.add_parser(
        "all",
        help="Run every job in matrix order, then ruff. Stops on first failure.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "all":
        run_all()
        return 0
    if args.command == "ruff":
        run_ruff()
        return 0

    job = next((j for j in JOBS if j["key"] == args.command), None)
    if job is None:
        parser.error(f"unknown command: {args.command}")
    run_job(job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
