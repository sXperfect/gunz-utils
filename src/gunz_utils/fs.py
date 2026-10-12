"""Production-safe filesystem helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import errno
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .io import atomic_write


def contained_path(
    root: str | Path,
    path: str | Path,
) -> Path:
    """Resolve a path and require it to remain inside root.

    Parameters
    ----------
    root : str | Path
        root parameter.
    path : str | Path
        path parameter.

    Returns
    -------
    Path
        The result of the operation.
    """
    base = Path(root).resolve()
    supplied = Path(path)
    if supplied.is_absolute():
        candidate = supplied.resolve()
    else:
        candidate = (base / supplied).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError("path escapes configured root") from None
    return candidate


def lexical_contained_path(
    root: str | Path,
    path: str | Path,
) -> Path:
    """Require a relative path to remain lexically below root.

    Parameters
    ----------
    root : str | Path
        root parameter.
    path : str | Path
        path parameter.

    Returns
    -------
    Path
        The result of the operation.
    """
    supplied = Path(path)
    if supplied.is_absolute():
        raise ValueError("path must be relative")
    if any(part == ".." for part in supplied.parts):
        raise ValueError("path escapes configured root")
    candidate = Path(root) / supplied
    #? Security: a lexical path can still escape root when an intermediate
    #? component is a symlink pointing outside. Resolve and require containment
    #? so callers are never handed a path that reads outside the configured root.
    base = Path(root).resolve()
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(base):
        raise ValueError("path escapes configured root")
    return candidate


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
) -> None:
    """Write bytes durably through the canonical atomic-write implementation.

    Parameters
    ----------
    path : str | Path
        path parameter.
    data : bytes
        data parameter.
    """
    atomic_write(
        path,
        data,
        mode="wb",
        mkdir=True,
        durable=True,
    )


def _rename_directory_noreplace(
    source: Path,
    target: Path,
) -> None:
    """Use an OS no-replace rename, failing closed when unavailable.

    Parameters
    ----------
    source : Path
        source parameter.
    target : Path
        target parameter.
    """
    if os.name == "nt":
        #? Windows rename rejects an existing destination atomically.
        os.rename(source, target)
        return

    import ctypes

    source_bytes = os.fsencode(source)
    target_bytes = os.fsencode(target)
    if b"\0" in source_bytes or b"\0" in target_bytes:
        raise ValueError("paths must not contain NUL")
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        function = getattr(library, "renameat2", None)
        if function is None:
            raise NotImplementedError("atomic no-replace rename is unavailable")
        function.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_int
        #? AT_FDCWD = -100; RENAME_NOREPLACE = 1.
        result = function(-100, source_bytes, -100, target_bytes, 1)
    elif sys.platform == "darwin":
        function = getattr(library, "renamex_np", None)
        if function is None:
            raise NotImplementedError("atomic no-replace rename is unavailable")
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        #? RENAME_EXCL = 0x00000004.
        result = function(source_bytes, target_bytes, 4)
    else:
        raise NotImplementedError("atomic no-replace rename is unavailable")
    if result != 0:
        error = ctypes.get_errno()
        if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise NotImplementedError(
                "filesystem does not support atomic no-replace rename"
            )
        raise OSError(error, os.strerror(error), str(target))


@contextmanager
def transactional_directory(
    path: str | Path,
) -> Iterator[Path]:
    """Build privately and publish atomically without replacing any target.

    Requires Windows rename, Linux renameat2/RENAME_NOREPLACE, or macOS
    renamex_np/RENAME_EXCL support. Unsupported platforms/filesystems raise
    NotImplementedError and clean staging. Parent directories must be trusted;
    this helper does not anchor their identity against malicious replacement.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}."))
    try:
        yield staging
        #? Security (VULN-2026-010): reject pre-existing targets, including
        #? symlinks, before publishing the staged directory.
        if target.is_symlink() or target.exists():
            raise FileExistsError(target)
        _rename_directory_noreplace(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


__all__ = [
    "atomic_write_bytes",
    "contained_path",
    "lexical_contained_path",
    "transactional_directory",
]
