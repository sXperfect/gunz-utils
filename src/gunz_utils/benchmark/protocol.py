"""Versioned benchmark worker protocol."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

WORKER_PROTOCOL_VERSION = 1


@dataclass(frozen=True, slots=True)
class WorkerRequest:
    module: str
    arguments: tuple[str, ...] = ()
    seed: int | None = None
    environment: dict[str, str] = field(default_factory=dict)
    protocol_version: int = WORKER_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.module, str) or not self.module:
            raise ValueError("module must be a non-empty string")
        object.__setattr__(self, "arguments", tuple(self.arguments))
        object.__setattr__(self, "environment", dict(self.environment))

    def to_dict(self) -> dict[str, Any]:
        """to_dict() function.

        Returns
        -------
        dict[str, Any]
            The result of the operation.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerRequest:
        """Create a WorkerRequest from a dictionary."""
        return cls(
            module=data["module"],
            arguments=tuple(data.get("arguments", ())),
            seed=data.get("seed"),
            environment=dict(data.get("environment", {})),
            protocol_version=data.get("protocol_version", WORKER_PROTOCOL_VERSION),
        )


@dataclass(frozen=True, slots=True)
class WorkerResponse:
    returncode: int
    payload: Any = None
    stderr: str = ""
    crashed: bool = False
    protocol_version: int = WORKER_PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        """to_dict() function.

        Returns
        -------
        dict[str, Any]
            The result of the operation.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerResponse:
        """Create a WorkerResponse from a dictionary."""
        return cls(
            returncode=data["returncode"],
            payload=data.get("payload"),
            stderr=data.get("stderr", ""),
            crashed=data.get("crashed", False),
            protocol_version=data.get("protocol_version", WORKER_PROTOCOL_VERSION),
        )


__all__ = [
    "WORKER_PROTOCOL_VERSION",
    "WorkerRequest",
    "WorkerResponse",
]
