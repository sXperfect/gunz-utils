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


__all__ = ["register_artifact"]
