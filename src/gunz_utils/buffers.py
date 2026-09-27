"""Zero-copy buffer utilities and backend dispatch."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def as_readonly_view(data: bytes | bytearray | memoryview) -> memoryview:
    """Return a byte-oriented readonly view without copying when possible."""
    view = memoryview(data).cast("B")
    return view.toreadonly()


def dispatch(
    reference: Callable[..., T],
    accelerated: Callable[..., T] | None = None,
) -> Callable[..., T]:
    """Select an optional accelerated implementation without making it required."""
    return accelerated or reference


__all__ = ["as_readonly_view", "dispatch"]
