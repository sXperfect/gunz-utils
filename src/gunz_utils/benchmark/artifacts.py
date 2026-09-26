"""Portable performance-run artifact registry."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from .performance import PerformanceArtifact, PerformanceRun


def register_artifact(
    run: PerformanceRun,
    path: str | Path,
    *,
    kind: str,
    media_type: str | None = None,
    description: str | None = None,
) -> PerformanceRun:
    """Attach a checksummed artifact to a performance run."""
    item = Path(path)
    digest = hashlib.sha256(item.read_bytes()).hexdigest()
    artifact = PerformanceArtifact(
        kind=kind,
        path=str(item),
        media_type=media_type,
        description=description,
        checksum_sha256=digest,
        size_bytes=item.stat().st_size,
    )
    return replace(run, artifacts=(*run.artifacts, artifact))


def verify_artifact(artifact: PerformanceArtifact) -> bool:
    """Verify artifact existence, recorded size and SHA-256 checksum."""
    if artifact.checksum_sha256 is None or artifact.size_bytes is None:
        return False
    item = Path(artifact.path)
    try:
        if item.stat().st_size != artifact.size_bytes:
            return False
        digest = hashlib.sha256(item.read_bytes()).hexdigest()
    except OSError:
        return False
    return digest == artifact.checksum_sha256


__all__ = ["register_artifact", "verify_artifact"]
