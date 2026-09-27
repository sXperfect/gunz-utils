"""Production-safe filesystem helpers."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def contained_path(root: str | Path, path: str | Path) -> Path:
    """Resolve a path and require it to remain inside root."""
    base = Path(root).resolve()
    supplied = Path(path)
    candidate = (base / supplied).resolve() if not supplied.is_absolute() else supplied.resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError("path escapes configured root") from None
    return candidate


def lexical_contained_path(root: str | Path, path: str | Path) -> Path:
    """Require a relative path to remain lexically below root."""
    supplied = Path(path)
    if supplied.is_absolute():
        raise ValueError("path must be relative")
    if any(part == ".." for part in supplied.parts):
        raise ValueError("path escapes configured root")
    return Path(root) / supplied


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write bytes using fsync and same-directory atomic replacement."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def transactional_directory(path: str | Path) -> Iterator[Path]:
    """Build a directory privately and atomically publish it on success."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}."))
    try:
        yield staging
        if target.exists():
            raise FileExistsError(target)
        os.replace(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


__all__ = [
    "atomic_write_bytes",
    "contained_path",
    "lexical_contained_path",
    "transactional_directory",
]
