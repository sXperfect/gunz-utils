"""JSON persistence and git provenance for benchmark artifacts."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ..subprocess import (
    CommandError,
    CommandOutputLimitError,
    run_command,
)
from .result import BenchmarkResult
from .safe_io import DEFAULT_MAX_RESULT_BYTES, load_result_checked


@dataclass(frozen=True)
class GitInfo:
    """Repository provenance attached to a benchmark run."""

    commit: str | None
    branch: str | None
    dirty: bool | None


def capture_git_info(
    cwd: str | None = None,
) -> GitInfo:
    """Capture git revision metadata without requiring GitPython.

    Parameters
    ----------
    cwd : str | None
        cwd parameter.

    Returns
    -------
    GitInfo
        The result of the operation.
    """
    def run(
        *args: str,
    ) -> str | None:
        """run() function.

        Parameters
        ----------
        args : str
            args parameter.

        Returns
        -------
        str | None
            The result of the operation.
        """
        try:
            result = run_command(
                ["git", *args],
                cwd=cwd,
                check=True,
                timeout=5.0,
                max_output_bytes=1024 * 1024,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
            CommandError,
            CommandOutputLimitError,
        ):
            return None
        return result.stdout.strip()

    commit = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--porcelain")
    return GitInfo(
        commit=commit,
        branch=branch or None,
        dirty=None if status is None else bool(status),
    )


def save_result(
    result: BenchmarkResult,
    path: str | Path,
) -> None:
    """Persist a benchmark result as stable indented JSON.

    Parameters
    ----------
    result : BenchmarkResult
        result parameter.
    path : str | Path
        path parameter.
    """
    Path(path).write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_result(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
) -> BenchmarkResult:
    """Load and validate a benchmark result within a bounded input size.

    Parameters
    ----------
    path : str | Path
        path parameter.
    max_bytes : int
        max_bytes parameter.

    Returns
    -------
    BenchmarkResult
        The result of the operation.
    """
    return load_result_checked(path, max_bytes=max_bytes)


__all__ = ["GitInfo", "capture_git_info", "load_result", "save_result"]
