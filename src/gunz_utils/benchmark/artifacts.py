"""Portable performance-run artifact registry."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from .performance import PerformanceArtifact, PerformanceRun


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def register_artifact(
    run: PerformanceRun,
    path: str | Path,
    *,
    kind: str,
    media_type: str | None = None,
    description: str | None = None,
) -> PerformanceRun:
    """Attach a checksummed regular-file artifact to a performance run."""
    item = Path(path)
    if item.is_symlink() or not item.is_file():
        raise ValueError("artifact must be a non-symlink regular file")
    stat = item.stat()
    artifact = PerformanceArtifact(
        kind=kind,
        path=str(item),
        media_type=media_type,
        description=description,
        checksum_sha256=_sha256_file(item),
        size_bytes=stat.st_size,
    )
    return replace(run, artifacts=(*run.artifacts, artifact))


def verify_artifact(artifact: PerformanceArtifact) -> bool:
    """Verify artifact existence, size and SHA-256 checksum with bounded memory."""
    if artifact.checksum_sha256 is None or artifact.size_bytes is None:
        return False
    item = Path(artifact.path)
    try:
        if (
            item.is_symlink()
            or not item.is_file()
            or item.stat().st_size != artifact.size_bytes
        ):
            return False
        digest = _sha256_file(item)
    except OSError:
        return False
    return digest == artifact.checksum_sha256


__all__ = ["register_artifact", "verify_artifact"]
