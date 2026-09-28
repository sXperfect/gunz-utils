"""JSON persistence and git provenance for benchmark artifacts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from .result import BenchmarkResult
from .safe_io import DEFAULT_MAX_RESULT_BYTES, load_result_checked


@dataclass(frozen=True)
class GitInfo:
    """Repository provenance attached to a benchmark run."""

    commit: str | None
    branch: str | None
    dirty: bool | None


def capture_git_info(cwd: str | None = None) -> GitInfo:
    """Capture git revision metadata without requiring GitPython."""
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
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


def save_result(result: BenchmarkResult, path: str | Path) -> None:
    """Persist a benchmark result as stable indented JSON."""
    Path(path).write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_result(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
) -> BenchmarkResult:
    """Load and validate a benchmark result within a bounded input size."""
    return load_result_checked(path, max_bytes=max_bytes)


__all__ = ["GitInfo", "capture_git_info", "load_result", "save_result"]
