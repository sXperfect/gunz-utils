"""Canonical filesystem utilities and advisory locking (alias for gunz_utils.fs)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .fs import (
    TemporaryDirectoryPool,
    advisory_file_lock,
    atomic_write_bytes,
    contained_path,
    copy_file_atomic,
    ensure_dir,
    ensure_directory,
    file_size_bytes,
    find_files,
    get_disk_usage,
    is_file_locked,
    lexical_contained_path,
    match_path_glob,
    matches_any_glob,
    safe_remove,
    safe_rmtree,
    touch_file,
    transactional_directory,
    tree_fingerprint,
    walk_directory,
    walk_files,
)

__all__ = [
    "TemporaryDirectoryPool",
    "advisory_file_lock",
    "atomic_write_bytes",
    "contained_path",
    "copy_file_atomic",
    "ensure_dir",
    "ensure_directory",
    "file_size_bytes",
    "find_files",
    "get_disk_usage",
    "is_file_locked",
    "lexical_contained_path",
    "match_path_glob",
    "matches_any_glob",
    "safe_remove",
    "safe_rmtree",
    "touch_file",
    "transactional_directory",
    "tree_fingerprint",
    "walk_directory",
    "walk_files",
]
