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


def is_aware(
    dt: datetime,
) -> bool:
    """Return True if the datetime is timezone-aware."""
    if not isinstance(dt, datetime):
        raise TypeError(f"expected datetime, got {type(dt).__name__}")
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def to_iso_utc(
    dt: datetime,
) -> str:
    """Format any datetime to canonical ISO 8601 UTC ending in 'Z'.

    Naive datetimes are assumed to be in UTC. Aware datetimes in other timezones
    are converted to UTC before formatting.
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"expected datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        utc_dt = dt.replace(tzinfo=UTC)
    else:
        utc_dt = dt.astimezone(UTC)
    iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%S")
    if utc_dt.microsecond:
        iso += f".{utc_dt.microsecond:06d}"
    return iso + "Z"


def from_iso_utc(
    iso_str: str,
) -> datetime:
    """Parse an ISO 8601 string into an aware datetime in UTC."""
    if not isinstance(iso_str, str):
        raise TypeError(f"expected str, got {type(iso_str).__name__}")
    clean = iso_str.strip()
    if not clean:
        raise ValueError("empty ISO datetime string")
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(clean)
    except ValueError as exc:
        raise ValueError(f"invalid ISO 8601 datetime: {iso_str!r}") from exc
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_unix_seconds(
    dt: datetime,
) -> float:
    """Return POSIX timestamp in seconds from a datetime."""
    if not isinstance(dt, datetime):
        raise TypeError(f"expected datetime, got {type(dt).__name__}")
    if not is_aware(dt):
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def from_unix_seconds(
    timestamp: float,
) -> datetime:
    """Return an aware UTC datetime from a POSIX timestamp in seconds."""
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not math.isfinite(float(timestamp))
    ):
        raise ValueError("timestamp must be a finite number")
    return datetime.fromtimestamp(float(timestamp), tz=UTC)


def to_unix_millis(
    dt: datetime,
) -> int:
    """Return POSIX timestamp in milliseconds from a datetime."""
    return int(to_unix_seconds(dt) * 1000)


def from_unix_millis(
    ms: int,
) -> datetime:
    """Return an aware UTC datetime from a millisecond POSIX timestamp."""
    if isinstance(ms, bool) or not isinstance(ms, int):
        raise TypeError("ms must be an integer")
    return from_unix_seconds(ms / 1000.0)


def clamp_datetime(
    dt: datetime,
    min_dt: datetime | None = None,
    max_dt: datetime | None = None,
) -> datetime:
    """Clamp a datetime within an optional [min_dt, max_dt] interval."""
    if not isinstance(dt, datetime):
        raise TypeError(f"expected datetime, got {type(dt).__name__}")
    if min_dt is not None:
        if not isinstance(min_dt, datetime):
            raise TypeError("min_dt must be a datetime or None")
        if dt < min_dt:
            return min_dt
    if max_dt is not None:
        if not isinstance(max_dt, datetime):
            raise TypeError("max_dt must be a datetime or None")
        if dt > max_dt:
            return max_dt
    return dt


__all__ = [
    "clamp_datetime",
    "expired",
    "from_iso_utc",
    "from_unix_millis",
    "from_unix_seconds",
    "is_aware",
    "monotonic_deadline",
    "remaining",
    "to_iso_utc",
    "to_unix_millis",
    "to_unix_seconds",
    "utc_now",
]
