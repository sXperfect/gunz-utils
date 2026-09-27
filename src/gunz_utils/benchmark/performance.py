"""Unified performance-run model for normalized measurements and artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .io import GitInfo
from .process import ProcessProfile
from .result import BenchmarkResult, SystemInfo


@dataclass(frozen=True)
class PerformanceArtifact:
    """External or generated artifact associated with a performance run."""

    kind: str
    path: str
    media_type: str | None = None
    description: str | None = None
    checksum_sha256: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class PerformanceRun:
    """Normalized envelope joining timing, resources, provenance and artifacts."""

    name: str
    system: SystemInfo
    git: GitInfo | None = None
    benchmark: BenchmarkResult | None = None
    process_profile: ProcessProfile | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float | int | None] = field(default_factory=dict)
    artifacts: tuple[PerformanceArtifact, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return an envelope whose array fields satisfy the persisted schema."""
        data = asdict(self)
        data["artifacts"] = list(data["artifacts"])
        data["warnings"] = list(data["warnings"])
        return data


__all__ = ["PerformanceArtifact", "PerformanceRun"]
