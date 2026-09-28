"""Portable performance-run artifact registry."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import replace
from pathlib import Path

from .performance import PerformanceArtifact, PerformanceRun


def _hash_regular_file(
    path: Path,
    chunk_size: int = 1 << 20,
) -> tuple[str, int]:
    """Hash an opened regular file without following a final symlink."""
    if path.is_symlink():
        raise ValueError("artifact must be a non-symlink regular file")
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if path.is_symlink():
            raise ValueError(
                "artifact must be a non-symlink regular file"
            ) from exc
        raise
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("artifact must be a non-symlink regular file")
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            while chunk := handle.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest(), info.st_size
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def register_artifact(
    run: PerformanceRun,
    path: str | Path,
    *,
    kind: str,
    media_type: str | None = None,
    description: str | None = None,
) -> PerformanceRun:
    """Attach a checksummed non-symlink regular-file artifact to a run."""
    item = Path(path)
    checksum, size_bytes = _hash_regular_file(item)
    artifact = PerformanceArtifact(
        kind=kind,
        path=str(item),
        media_type=media_type,
        description=description,
        checksum_sha256=checksum,
        size_bytes=size_bytes,
    )
    return replace(run, artifacts=(*run.artifacts, artifact))


def verify_artifact(artifact: PerformanceArtifact) -> bool:
    """Verify artifact type, size, and SHA-256 checksum with bounded memory."""
    if artifact.checksum_sha256 is None or artifact.size_bytes is None:
        return False
    try:
        digest, size_bytes = _hash_regular_file(Path(artifact.path))
    except (OSError, ValueError):
        return False
    return (
        size_bytes == artifact.size_bytes
        and digest == artifact.checksum_sha256
    )


__all__ = ["register_artifact", "verify_artifact"]
