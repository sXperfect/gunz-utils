"""Timezone-safe time and deadline helpers."""

from __future__ import annotations

import time
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware current UTC datetime."""
    return datetime.now(UTC)


def monotonic_deadline(timeout: float) -> float:
    """Return a monotonic-clock deadline timeout seconds from now."""
    if timeout < 0:
        raise ValueError("timeout must be non-negative")
    return time.monotonic() + timeout


def remaining(deadline: float) -> float:
    """Return non-negative seconds remaining before a monotonic deadline."""
    return max(0.0, deadline - time.monotonic())


def expired(deadline: float) -> bool:
    """Return whether a monotonic deadline has elapsed."""
    return remaining(deadline) == 0.0


__all__ = ["expired", "monotonic_deadline", "remaining", "utc_now"]
