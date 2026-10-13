"""Timezone-safe time and deadline helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import time
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
) -> float:
    """Return a monotonic-clock deadline timeout seconds from now.

    Parameters
    ----------
    timeout : float
        timeout parameter.

    Returns
    -------
    float
        The result of the operation.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("timeout must be a finite non-negative number")
    try:
        numeric = float(timeout)
    except OverflowError:
        raise ValueError(
            "timeout must be a finite non-negative number"
        ) from None
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError("timeout must be a finite non-negative number")
    return time.monotonic() + numeric


def remaining(
    deadline: float,
) -> float:
    """Return non-negative seconds remaining before a monotonic deadline.

    Parameters
    ----------
    deadline : float
        deadline parameter.

    Returns
    -------
    float
        The result of the operation.
    """
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
        raise ValueError("deadline must be a finite number")
    try:
        numeric = float(deadline)
    except OverflowError:
        raise ValueError("deadline must be a finite number") from None
    if not math.isfinite(numeric):
        raise ValueError("deadline must be a finite number")
    return max(0.0, numeric - time.monotonic())


def expired(
    deadline: float,
) -> bool:
    """Return whether a monotonic deadline has elapsed.

    Parameters
    ----------
    deadline : float
        deadline parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
    return remaining(deadline) <= 0.0


__all__ = ["expired", "monotonic_deadline", "remaining", "utc_now"]
