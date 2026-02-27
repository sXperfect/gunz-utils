"""
Project environment and path resolution utilities.

This module provides robust methods to locate the project root dynamically,
ensuring scripts run correctly regardless of their execution directory.
"""

#? Metadata
__author__ = "Yeremia Gunawan Adhisantoso"
__version__ = "1.0.0"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import pathlib
import sys
import typing as t

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from git import Repo, InvalidGitRepositoryError
from loguru import logger

#? Cache the root to avoid repeated disk I/O
_PROJECT_ROOT: t.Optional[pathlib.Path] = None


def resolve_project_root(
    anchor: str = ".",
    inject_to_sys_path: bool = True,
) -> pathlib.Path:
    """
    Dynamically finds the git repository root and optionally adds it to sys.path.

    This allows scripts to import local modules (e.g., `src.pekora`) without
    hardcoding relative paths.

    Parameters
    ----------
    anchor : str, optional
        The path to start searching from, by default current working directory.
    inject_to_sys_path : bool, optional
        If True, adds the root directory to `sys.path` to enable imports,
        by default True.

    Returns
    -------
    pathlib.Path
        The absolute path to the project root.

    Raises
    ------
    RuntimeError
        If the git repository root cannot be found.
    """
    global _PROJECT_ROOT

    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    try:
        #? Search upwards for the .git directory
        repo = Repo(anchor, search_parent_directories=True)
        root_path = pathlib.Path(repo.working_tree_dir).resolve()

        #? Validate it's actually a directory
        if not root_path.is_dir():
            raise RuntimeError(f"Resolved root is not a directory: {root_path}")

        _PROJECT_ROOT = root_path

        if inject_to_sys_path:
            root_str = str(root_path)
            if root_str not in sys.path:
                #? Insert at position 0 to prioritize local source over installed packages
                sys.path.insert(0, root_str)
                logger.debug(f"Added project root to sys.path: {root_str}")

        return _PROJECT_ROOT

    except InvalidGitRepositoryError:
        raise RuntimeError(
            "Could not find project root. Ensure you are running inside a git repository."
        )
    except Exception as e:
        raise RuntimeError(f"Unexpected error resolving project root: {e}")
