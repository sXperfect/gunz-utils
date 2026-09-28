"""Production-safe filesystem helpers."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .io import atomic_write


def contained_path(root: str | Path, path: str | Path) -> Path:
    """Resolve a path and require it to remain inside root."""
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


def lexical_contained_path(root: str | Path, path: str | Path) -> Path:
    """Require a relative path to remain lexically below root."""
    supplied = Path(path)
    if supplied.is_absolute():
        raise ValueError("path must be relative")
    if any(part == ".." for part in supplied.parts):
        raise ValueError("path escapes configured root")
    return Path(root) / supplied


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write bytes durably through the canonical atomic-write implementation."""
    atomic_write(
        path,
        data,
        mode="wb",
        mkdir=True,
        durable=True,
    )


@contextmanager
def transactional_directory(path: str | Path) -> Iterator[Path]:
    """Build a directory privately and atomically publish it on success."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}."))
    try:
        yield staging
        # Security (VULN-2026-010): reject pre-existing targets, including
        # symlinks, before publishing the staged directory.
        if target.is_symlink() or target.exists():
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
