"""Stdlib-only analog of `gunz_utils.ext.project_gitpython.resolve_project_root`.

Walks up from `anchor` looking for `.git` / `pyproject.toml`; falls back
to `subprocess.run(["git", "rev-parse", "--show-toplevel"], timeout=5)`.
No gitpython import, no loguru import.
"""
from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
import functools
import pathlib
import subprocess
import sys

from .._version import __version__ as __version__
from ..subprocess import CommandError, CommandOutputLimitError, run_command

__all__ = ["resolve_project_root"]

_PROJECT_ROOT: pathlib.Path | None = None
_PROJECT_ANCHOR: pathlib.Path | None = None


@functools.lru_cache(maxsize=1)
def _git_rev_parse_toplevel(anchor: str) -> pathlib.Path | None:
    try:
        result = run_command(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            timeout=5.0,
            cwd=anchor,
            max_output_bytes=1024 * 1024,
        )
        return pathlib.Path(result.stdout.strip()).resolve()
    except (
        CommandError,
        CommandOutputLimitError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError,
    ):
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
    global _PROJECT_ANCHOR, _PROJECT_ROOT

    start = pathlib.Path(anchor).resolve()
    if (
        _PROJECT_ROOT is not None
        and _PROJECT_ANCHOR is not None
        and (start == _PROJECT_ROOT or _PROJECT_ROOT in start.parents)
    ):
        if inject_to_sys_path:
            root_str = str(_PROJECT_ROOT)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
        return _PROJECT_ROOT
    root = _walk_up_for_marker(start) or _git_rev_parse_toplevel(str(start))
    if root is None:
        raise RuntimeError(
            "Could not find project root. Ensure you are running inside a "
            "git repository or near a pyproject.toml."
        )

    if not root.is_dir():
        raise RuntimeError(f"Resolved root is not a directory: {root}")

    _PROJECT_ROOT = root
    _PROJECT_ANCHOR = start

    if inject_to_sys_path:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    return _PROJECT_ROOT
