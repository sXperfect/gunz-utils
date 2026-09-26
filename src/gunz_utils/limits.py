"""Reusable resource limits for defensive parsing and processing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_bytes: int | None = None
    max_items: int | None = None
    max_depth: int | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        for name in ("max_bytes", "max_items", "max_depth"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.timeout is not None and self.timeout < 0:
            raise ValueError("timeout must be non-negative")

    def check_bytes(self, size: int) -> None:
        if self.max_bytes is not None and size > self.max_bytes:
            raise ValueError("byte limit exceeded")

    def check_items(self, count: int) -> None:
        if self.max_items is not None and count > self.max_items:
            raise ValueError("item limit exceeded")


__all__ = ["Limits"]
