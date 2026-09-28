"""Isolated benchmark worker execution using the Python standard library."""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from ..subprocess import run_command


@dataclass(frozen=True)
class WorkerResult:
    """Result returned by an isolated benchmark worker process."""

    returncode: int
    stdout: str
    stderr: str


def run_python_worker(
    module: str,
    *,
    args: Sequence[str] = (),
    python: str = sys.executable,
    timeout: float | None = None,
    max_output_bytes: int | None = 8 * 1024 * 1024,
) -> WorkerResult:
    """Execute a trusted benchmark module with bounded captured output."""
    if not isinstance(module, str) or not module:
        raise ValueError("module must be a non-empty string")
    if not isinstance(python, str) or not python:
        raise ValueError("python must be a non-empty string")

    # ? Security (VULN-2026-009): Validate python interpreter path to reject
    # ? leading dashes ('-') or control characters that could inject subshell flags.
    if python.strip().startswith("-"):
        raise ValueError("python binary path must not start with a dash")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in python):
        raise ValueError("python binary path contains invalid control characters")
    if any(not isinstance(argument, str) for argument in args):
        raise ValueError("args must contain strings")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout <= 0
    ):
        raise ValueError("timeout must be a finite positive number or None")
    completed = run_command(
        [python, "-m", module, *args],
        timeout=timeout,
        max_output_bytes=max_output_bytes,
    )
    return WorkerResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def worker_json(result: WorkerResult) -> object:
    """Decode a successful worker's stdout as strict JSON."""
    if result.returncode:
        raise RuntimeError(
            f"benchmark worker failed with exit code {result.returncode}"
        )
    return json.loads(result.stdout, parse_constant=_reject_json_constant)


__all__ = ["WorkerResult", "run_python_worker", "worker_json"]
