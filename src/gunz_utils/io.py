"""Crash-safe file writing utilities for the Gunz ecosystem."""

from __future__ import annotations

import os
import pathlib
import tempfile
from typing import Any

from ._version import __version__
from .serialization import json_dumps

__author__ = "Yeremia Gunz"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = ["atomic_json_write", "atomic_write"]


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
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
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
        if is_binary:
            with os.fdopen(fd, mode) as file:
                file.write(content)
                if durable:
                    file.flush()
                    os.fsync(file.fileno())
        else:
            with os.fdopen(fd, mode, encoding=encoding or "utf-8") as file:
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
