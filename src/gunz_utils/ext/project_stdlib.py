"""Stdlib-only analog of `gunz_utils.ext.project_gitpython.resolve_project_root`.

Walks up from `anchor` looking for `.git` / `pyproject.toml`; falls back
to `subprocess.run(["git", "rev-parse", "--show-toplevel"], timeout=5)`.
No gitpython import, no loguru import.
"""
from __future__ import annotations

import functools
import pathlib
import subprocess
import sys
import typing as t

__all__ = ["resolve_project_root"]

_PROJECT_ROOT: t.Optional[pathlib.Path] = None


@functools.lru_cache(maxsize=1)
def _git_rev_parse_toplevel(anchor: str) -> pathlib.Path | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            cwd=anchor,
        )
        return pathlib.Path(r.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _walk_up_for_marker(start: pathlib.Path) -> pathlib.Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate.resolve()
    return None


def resolve_project_root(
    anchor: str = ".",
    inject_to_sys_path: bool = True,
) -> pathlib.Path:
    """Return the project root for `anchor`.

    Strategy:
      1. Walk up looking for `.git` or `pyproject.toml`.
      2. Subprocess fallback `git rev-parse --show-toplevel` (5s timeout).
      3. Raise `RuntimeError`.

    Caches the result. When `inject_to_sys_path` is True, inserts the
    resolved root at `sys.path[0]` (deduped).
    """
    global _PROJECT_ROOT

    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    start = pathlib.Path(anchor).resolve()
    root = _walk_up_for_marker(start) or _git_rev_parse_toplevel(str(start))
    if root is None:
        raise RuntimeError(
            "Could not find project root. Ensure you are running inside a git repository "
            "or near a pyproject.toml."
        )

    if not root.is_dir():
        raise RuntimeError(f"Resolved root is not a directory: {root}")

    _PROJECT_ROOT = root

    if inject_to_sys_path:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    return _PROJECT_ROOT