"""Unified performance-run model for normalized measurements and artifacts."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "metrics", dict(self.metrics))

    def to_dict(self) -> dict[str, Any]:
        """Return an envelope whose array fields satisfy the persisted schema.

        Returns
        -------
        dict[str, Any]
            The result of the operation.
        """
        data = asdict(self)
        data["artifacts"] = list(data["artifacts"])
        data["warnings"] = list(data["warnings"])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerformanceRun:
        """Reconstruct a PerformanceRun from a serialized dictionary."""
        artifacts = tuple(
            PerformanceArtifact(**art) if isinstance(art, dict) else art
            for art in data.get("artifacts", ())
        )
        system_data = data["system"]
        system = (
            SystemInfo(**system_data)
            if isinstance(system_data, dict)
            else system_data
        )
        git_data = data.get("git")
        git = (
            GitInfo(**git_data)
            if isinstance(git_data, dict)
            else git_data
        )
        return cls(
            name=data["name"],
            system=system,
            git=git,
            parameters=dict(data.get("parameters", {})),
            metrics=dict(data.get("metrics", {})),
            artifacts=artifacts,
            warnings=tuple(data.get("warnings", ())),
            schema_version=data.get("schema_version", 1),
        )


__all__ = ["PerformanceArtifact", "PerformanceRun"]
