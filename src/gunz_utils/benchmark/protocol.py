"""Versioned benchmark worker protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

WORKER_PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class WorkerRequest:
    module: str
    arguments: tuple[str, ...] = ()
    seed: int | None = None
    environment: dict[str, str] = field(default_factory=dict)
    protocol_version: int = WORKER_PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkerResponse:
    returncode: int
    payload: Any = None
    stderr: str = ""
    crashed: bool = False
    protocol_version: int = WORKER_PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "WORKER_PROTOCOL_VERSION",
    "WorkerRequest",
    "WorkerResponse",
]
