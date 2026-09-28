"""Isolated benchmark worker execution using the Python standard library."""

from __future__ import annotations

import json
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


def worker_json(result: WorkerResult) -> object:
    """Decode a successful worker's stdout as JSON."""
    if result.returncode:
        raise RuntimeError(
            f"benchmark worker failed with exit code {result.returncode}"
        )
    return json.loads(result.stdout)


__all__ = ["WorkerResult", "run_python_worker", "worker_json"]
