"""Timezone-safe time and deadline helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware current UTC datetime.

    Returns
    -------
    datetime
        The result of the operation.
    """
    return datetime.now(UTC)


def monotonic_deadline(
    timeout: float,
    *,
    clock: Callable[[], float] | None = None,
) -> float:
    """Return a monotonic-clock deadline timeout seconds from now.

    Parameters
    ----------
    timeout : float
        timeout parameter.
    clock : Callable[[], float] or None, optional
        Clock callable returning current time in seconds, by default time.monotonic.

    Returns
    -------
    float
        The result of the operation.
    """
    if clock is not None and not callable(clock):
        raise TypeError("clock must be callable")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        raise ValueError("timeout must be a finite non-negative number")
    now = clock() if clock is not None else time.monotonic()
    deadline = now + float(timeout)
    if not math.isfinite(deadline):
        raise OverflowError("monotonic deadline calculation overflowed")
    return deadline


def remaining(
    deadline: float,
    *,
    clock: Callable[[], float] | None = None,
) -> float:
    """Return non-negative seconds remaining before a monotonic deadline.

    Parameters
    ----------
    deadline : float
        deadline parameter.
    clock : Callable[[], float] or None, optional
        Clock callable returning current time in seconds, by default time.monotonic.

    Returns
    -------
    float
        The result of the operation.
    """
    if clock is not None and not callable(clock):
        raise TypeError("clock must be callable")
    if (
        isinstance(deadline, bool)
        or not isinstance(deadline, (int, float))
        or not math.isfinite(float(deadline))
    ):
        raise ValueError("deadline must be a finite number")
    now = clock() if clock is not None else time.monotonic()
    return max(0.0, float(deadline) - now)


def expired(
    deadline: float,
    *,
    clock: Callable[[], float] | None = None,
) -> bool:
    """Return whether a monotonic deadline has elapsed.

    Parameters
    ----------
    deadline : float
        deadline parameter.
    clock : Callable[[], float] or None, optional
        Clock callable returning current time in seconds, by default time.monotonic.

    Returns
    -------
    bool
        The result of the operation.
    """
    if clock is not None and not callable(clock):
        raise TypeError("clock must be callable")
    return remaining(deadline, clock=clock) <= 0.0


__all__ = ["expired", "monotonic_deadline", "remaining", "utc_now"]
