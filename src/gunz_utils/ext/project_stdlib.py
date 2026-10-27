"""Stdlib-only analog of `gunz_utils.ext.project_gitpython.resolve_project_root`.

Walks up from `anchor` looking for `.git` / `pyproject.toml`; falls back
to `subprocess.run(["git", "rev-parse", "--show-toplevel"], timeout=5)`.
No gitpython import, no loguru import.
"""
# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

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
import typing as t

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .._version import __version__ as __version__
from ..subprocess import CommandError, CommandOutputLimitError, run_command

__all__ = ["resolve_project_root"]

_PROJECT_ROOT: pathlib.Path | None = None
_PROJECT_ANCHOR: pathlib.Path | None = None


@functools.lru_cache(maxsize=1)
def _git_rev_parse_toplevel(
    anchor: str,
) -> pathlib.Path | None:
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


def _walk_up_for_marker(
    start: pathlib.Path,
) -> pathlib.Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate.resolve()
    return None


def _build_injection_entries(
    root: pathlib.Path,
    src: bool,
    subpaths: t.Sequence[str | pathlib.Path],
) -> list[pathlib.Path]:
    """Build the ordered list of sys.path entries for a resolved root.

    The root comes first (lowest priority); `src` and each `subpath` are
    appended after it so they take higher import priority (inserted last wins
    the position-0 slot).

    Parameters
    ----------
    root : pathlib.Path
        The resolved project root.
    src : bool
        Whether to include ``root / "src"``.
    subpaths : t.Sequence[str | pathlib.Path]
        Additional relative subpaths of `root` to include.

    Returns
    -------
    list[pathlib.Path]
        The ordered list of paths to inject into ``sys.path``.
    """
    entries = [root]
    if src:
        entries.append(root / "src")
    for subpath in subpaths:
        entries.append(root / subpath)
    return entries


def _inject_to_sys_path(
    entries: list[pathlib.Path],
) -> None:
    """Insert resolved entries at the front of ``sys.path``, deduped.

    Later entries are inserted at position 0, so entries listed last end up
    with the highest import priority.

    Parameters
    ----------
    entries : list[pathlib.Path]
        The paths to inject, in priority order.
    """
    resolved: list[str] = []
    for entry in entries:
        path_str = str(entry)
        if path_str in sys.path or path_str in resolved:
            continue
        resolved.append(path_str)
    #? Intentional, documented, opt-in side effect of
    #? ``inject_to_sys_path`` (tested); not a hidden mutation.
    #? The entries are prepended in one slice assignment, so the import
    #? path is not rebuilt for every entry.
    sys.path[:0] = reversed(resolved)  # gunz-style: ignore[GS007]


def resolve_project_root(
    anchor: str = ".",
    inject_to_sys_path: bool = True,
    src: bool = False,
    subpaths: t.Sequence[str | pathlib.Path] = (),
) -> pathlib.Path:
    """Return the project root for `anchor`.

    Strategy:
      1. Walk up looking for `.git` or `pyproject.toml`.
      2. Subprocess fallback `git rev-parse --show-toplevel` (5s timeout).
      3. Raise `RuntimeError`.

    Parameters
    ----------
    anchor : str, optional
        The path to start searching from, by default current working directory.
    inject_to_sys_path : bool, optional
        If True, adds the root directory to `sys.path` to enable imports,
        by default True.
    src : bool, optional
        If True, also adds the ``src/`` subdirectory of the project root to
        ``sys.path`` (in addition to the root itself), enabling imports of
        package source laid out under ``src/``. By default False.
    subpaths : t.Sequence[str | pathlib.Path], optional
        Additional subdirectories of the project root to add to ``sys.path``
        (e.g. ``("scripts",)``). Each is resolved relative to the root and
        given higher import priority than the root. By default empty.

    Returns
    -------
    pathlib.Path
        The project root.

    Raises
    ------
    RuntimeError
        If the project root cannot be found.
    """
    global _PROJECT_ANCHOR, _PROJECT_ROOT

    start = pathlib.Path(anchor).resolve()
    if (
        _PROJECT_ROOT is not None
        and _PROJECT_ANCHOR is not None
        and (start == _PROJECT_ROOT or _PROJECT_ROOT in start.parents)
    ):
        if inject_to_sys_path:
            _inject_to_sys_path(
                _build_injection_entries(_PROJECT_ROOT, src, subpaths)
            )
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
        _inject_to_sys_path(_build_injection_entries(root, src, subpaths))

    return _PROJECT_ROOT
