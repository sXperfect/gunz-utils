"""Timezone-safe time and deadline helpers."""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware current UTC datetime."""
    return datetime.now(UTC)


def monotonic_deadline(timeout: float) -> float:
    """Return a monotonic-clock deadline timeout seconds from now."""
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        raise ValueError("timeout must be a finite non-negative number")
    return time.monotonic() + float(timeout)


def remaining(deadline: float) -> float:
    """Return non-negative seconds remaining before a monotonic deadline."""
    if (
        isinstance(deadline, bool)
        or not isinstance(deadline, (int, float))
        or not math.isfinite(float(deadline))
    ):
        raise ValueError("deadline must be a finite number")
    return max(0.0, float(deadline) - time.monotonic())


def expired(deadline: float) -> bool:
    """Return whether a monotonic deadline has elapsed."""
    return remaining(deadline) == 0.0


__all__ = ["expired", "monotonic_deadline", "remaining", "utc_now"]
