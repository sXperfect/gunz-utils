"""Isolated benchmark worker execution using the Python standard library."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence


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
) -> WorkerResult:
    """Execute a benchmark module in a fresh interpreter process."""
    completed = subprocess.run(
        [python, "-m", module, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
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
            f"benchmark worker failed with exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return json.loads(result.stdout)


__all__ = ["WorkerResult", "run_python_worker", "worker_json"]
