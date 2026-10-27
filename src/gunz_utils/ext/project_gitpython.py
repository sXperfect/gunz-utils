"""
Project environment and path resolution utilities.

This module provides robust methods to locate the project root dynamically,
ensuring scripts run correctly regardless of their execution directory.
"""

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import logging
import pathlib
import sys
import typing as t

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from git import InvalidGitRepositoryError, Repo

logger = logging.getLogger(__name__)

# ? Cache the root to avoid repeated disk I/O
_PROJECT_ROOT: pathlib.Path | None = None
_PROJECT_ANCHOR: pathlib.Path | None = None


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
        logger.debug("Added project path to sys.path: %s", path_str)
    #? Intentional, documented, opt-in side effect of
    #? ``inject_to_sys_path`` (tested); not a hidden mutation.
    #? The entries are prepended in one slice assignment, so the local
    #? source keeps priority over the installed packages and the import
    #? path is not rebuilt for every entry.
    sys.path[:0] = reversed(resolved)  # gunz-style: ignore[GS007]


def resolve_project_root(
    anchor: str = ".",
    inject_to_sys_path: bool = True,
    src: bool = False,
    subpaths: t.Sequence[str | pathlib.Path] = (),
) -> pathlib.Path:
    """
    Dynamically finds the git repository root and optionally adds it to sys.path.

    This allows scripts to import local project modules without hardcoding
    relative paths.

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
        The absolute path to the project root.

    Raises
    ------
    RuntimeError
        If the git repository root cannot be found.
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

    try:
        # ? Search upwards for the .git directory
        repo = Repo(start, search_parent_directories=True)
        #? working_tree_dir is typed as str | os.PathLike[str] | None by GitPython;
        #? bare repos expose None here, so guard explicitly.
        working_dir = repo.working_tree_dir
        if working_dir is None:
            raise RuntimeError(
                "Resolved repo has no working tree (bare repository)."
            )
        root_path = pathlib.Path(working_dir).resolve()

        # ? Validate it's actually a directory
        if not root_path.is_dir():
            raise RuntimeError(f"Resolved root is not a directory: {root_path}")

        _PROJECT_ROOT = root_path
        _PROJECT_ANCHOR = start

        if inject_to_sys_path:
            _inject_to_sys_path(
                _build_injection_entries(root_path, src, subpaths)
            )

        return _PROJECT_ROOT

    except InvalidGitRepositoryError as exc:
        raise RuntimeError(
            "Could not find project root. "
            "Ensure you are running inside a git repository."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Unexpected {type(exc).__name__} while resolving project root"
        ) from exc
