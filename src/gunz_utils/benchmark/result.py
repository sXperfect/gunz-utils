"""Versioned benchmark result data structures."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SystemInfo:
    """Machine/runtime metadata used to judge benchmark comparability."""

    python: str
    platform: str
    machine: str
    processor: str
    cpu_count: int | None

    @classmethod
    def capture(cls) -> SystemInfo:
        return cls(
            python=sys.version.split()[0],
            platform=platform.platform(),
            machine=platform.machine(),
            processor=platform.processor(),
            cpu_count=os.cpu_count(),
        )


@dataclass(frozen=True)
class BenchmarkStats:
    """Descriptive timing statistics in seconds."""

    minimum: float
    median: float
    mean: float
    p95: float
    p99: float
    maximum: float
    stddev: float
    ops_per_second: float


@dataclass(frozen=True)
class BenchmarkResult:
    """Portable benchmark result with raw samples and metadata."""

    name: str
    samples: tuple[float, ...]
    stats: BenchmarkStats
    warmup: int
    iterations: int
    system: SystemInfo
    parameters: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible result mapping."""
        return asdict(self)


__all__ = [
    "BenchmarkResult",
    "BenchmarkStats",
    "SCHEMA_VERSION",
    "SystemInfo",
]
