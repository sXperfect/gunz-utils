"""Crash-safe file writing utilities for the Gunz ecosystem."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import pathlib
import stat
import tempfile
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__
from .serialization import json_dumps

__author__ = "Yeremia Gunz"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = ["atomic_json_write", "atomic_write", "read_regular_bytes"]


def atomic_write(
    path: str | pathlib.Path,
    content: str | bytes,
    *,
    mode: str = "w",
    encoding: str | None = None,
    mkdir: bool = False,
    durable: bool = False,
    permissions: int | None = None,
) -> None:
    """Atomically write text or bytes through a same-directory temporary file.

    When permissions is provided, the temporary file receives that mode before
    any content is written, and the mode is preserved by atomic replacement.

    With ``durable=True`` the file is fsynced before replacement and the parent
    directory is fsynced afterwards. If that final directory fsync fails, the
    replacement may already be visible even though durability was not confirmed
    and this function raises.
    """
    if not isinstance(path, str | pathlib.Path):
        raise TypeError("path must be str or pathlib.Path")

    if permissions is not None:
        if (
            isinstance(permissions, bool)
            or not isinstance(permissions, int)
            or not 0 <= permissions <= 0o7777
        ):
            raise ValueError(
                "permissions must be an integer mode in the range 0..0o7777"
            )
        if not hasattr(os, "fchmod"):
            raise NotImplementedError(
                "explicit permissions require os.fchmod support"
            )

    target = pathlib.Path(path)
    if mkdir:
        #? Security (VULN-2026-002): when the target is owner-private,
        #? create missing parent directories with owner-private permissions too.
        private_target = (
            permissions is not None
            and (permissions & 0o077) == 0
        )
        dir_mode = 0o700 if private_target else 0o755
        target.parent.mkdir(parents=True, exist_ok=True, mode=dir_mode)
    elif not target.parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {target.parent}")

    is_binary = "b" in mode
    if is_binary and isinstance(content, str):
        raise ValueError("Binary mode requires bytes content")
    if not is_binary and isinstance(content, bytes):
        raise ValueError("Text mode requires str content")

    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        if permissions is not None:
            os.fchmod(
                fd,
                permissions,
            )
        file_handle = os.fdopen(
            fd, mode, encoding=None if is_binary else encoding or "utf-8",
            closefd=False,
        )
        #? Keep raw ownership even if wrapper construction closes an incomplete
        #? wrapper before raising (for example for an unknown text encoding).
        if is_binary:
            with file_handle as file:
                file.write(content)
                if durable:
                    file.flush()
                    os.fsync(file.fileno())
        else:
            with file_handle as file:
                file.write(content)
                if durable:
                    file.flush()
                    os.fsync(file.fileno())
        os.replace(tmp_path, target)
        if durable and hasattr(os, "O_DIRECTORY"):
            dir_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    finally:
        os.close(fd)


def atomic_json_write(
    path: str | pathlib.Path,
    value: Any,
    *,
    pretty: bool = True,
    mkdir: bool = False,
    durable: bool = False,
    permissions: int | None = None,
) -> None:
    """Serialize deterministic JSON and publish it atomically.

    Parameters
    ----------
    path : str | pathlib.Path
        Destination JSON path.
    value : Any
        Value accepted by gunz_utils.serialization.to_jsonable.
    pretty : bool, default=True
        Use indented JSON when true.
    mkdir : bool, default=False
        Create missing parent directories.
    durable : bool, default=False
        Flush file and parent-directory metadata before returning.
    permissions : int | None, default=None
        Explicit file mode applied before content is written.
    """
    atomic_write(
        path,
        json_dumps(value, pretty=pretty),
        mode="w",
        encoding="utf-8",
        mkdir=mkdir,
        durable=durable,
        permissions=permissions,
    )


def read_regular_bytes(
    path: str | pathlib.Path,
    *,
    max_bytes: int,
    label: str = "file",
) -> bytes:
    """Capture one bounded regular-file snapshot; never reopen it for decoding.

    The final path component must not be a symlink. Parent directories are
    trusted local paths, not a sandbox boundary. Check identity/size/timestamps
    before and after reading. A digest must be computed from these returned
    bytes, not from a separate open. This does not lock out writers or promise
    filesystem snapshots.

    Parameters
    ----------
    path : str | pathlib.Path
        Target regular file path to read.
    max_bytes : int
        Maximum permitted file size and payload bytes.
    label : str, default="file"
        Human-readable descriptor used in exception messages.

    Returns
    -------
    bytes
        Captured byte contents of the regular file.
    """
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    target = pathlib.Path(path)
    before_path = target.lstat()
    if not stat.S_ISREG(before_path.st_mode):
        raise ValueError(f"{label} must be a non-symlink regular file")
    flags = os.O_RDONLY
    for name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK", "O_BINARY"):
        flags |= getattr(os, name, 0)
    descriptor = os.open(target, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or not os.path.samestat(before_path, before)
        ):
            raise ValueError(f"{label} path changed during open")
        if before.st_size > max_bytes:
            raise ValueError(f"{label} exceeds size limit ({max_bytes} bytes)")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1 << 20))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > max_bytes:
            raise ValueError(f"{label} exceeds size limit ({max_bytes} bytes)")
        after = os.fstat(descriptor)
        after_path = target.lstat()
        signature_before = (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        signature_after = (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if (
            not stat.S_ISREG(after_path.st_mode)
            or not os.path.samestat(before, after_path)
            or signature_before != signature_after
            or len(payload) != after.st_size
        ):
            raise ValueError(f"{label} changed during read")
        return payload
    finally:
        os.close(descriptor)

