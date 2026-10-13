"""Small testing helpers with no test-framework dependency."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
import os
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager


@contextmanager
def temporary_env(
    values: Mapping[str, str | None],
) -> Iterator[None]:
    """Temporarily set or remove environment variables and restore them.

    This changes process-global state. Overlapping contexts across threads
    require caller synchronization; nested contexts restore in reverse order.

    Parameters
    ----------
    values : Mapping[str, str | None]
        values parameter.

    Returns
    -------
    Iterator[None]
        The result of the operation.
    """
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _validate_poll_args(
    timeout: float,
    interval: float,
) -> tuple[float, float]:
    """Validate and convert ``eventually`` poll timing, or raise ValueError.

    Returns
    -------
    tuple[float, float]
        The converted ``(timeout, interval)`` float values.
    """
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout < 0
        or isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or interval <= 0
    ):
        raise ValueError(
            "timeout must be finite and non-negative and interval "
            "must be finite and positive"
        )
    try:
        timeout_float = float(timeout)
        interval_float = float(interval)
    except OverflowError:
        #? An int too large to convert to float must surface as the
        #? documented ValueError, not leak an internal OverflowError.
        raise ValueError(
            "timeout must be finite and non-negative and interval "
            "must be finite and positive"
        ) from None
    if not math.isfinite(timeout_float) or not math.isfinite(interval_float):
        raise ValueError(
            "timeout must be finite and non-negative and interval "
            "must be finite and positive"
        )
    return timeout_float, interval_float


def eventually(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> None:
    """Wait until a predicate succeeds or raise TimeoutError.

    Polling is cooperative: a predicate invocation cannot be interrupted here
    and a successful invocation is accepted even if it returns after the timeout.

    Parameters
    ----------
    predicate : Callable[[], bool]
        predicate parameter.
    timeout : float
        timeout parameter.
    interval : float
        interval parameter.
    """
    timeout_float, interval_float = _validate_poll_args(timeout, interval)
    deadline = time.monotonic() + timeout_float
    while True:
        if predicate():
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("condition did not become true before timeout")
        time.sleep(interval_float)


async def eventually_async(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> None:
    """Poll an async predicate without blocking other tasks.

    Predicate invocations are cooperative and may outlast the polling timeout.
    Use an outer asyncio deadline when a hung predicate must be cancelled.

    Args:
        predicate: Async condition to check until it succeeds.
        timeout: Maximum polling duration in seconds.
        interval: Delay between unsuccessful checks in seconds.

    Raises:
        ValueError: If timeout is negative or interval is not positive.
        TimeoutError: If the condition remains false until the deadline.
    """
    timeout_float, interval_float = _validate_poll_args(timeout, interval)
    deadline = time.monotonic() + timeout_float
    while True:
        if await predicate():
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("condition did not become true before timeout")
        await asyncio.sleep(interval_float)


__all__ = ["eventually", "eventually_async", "temporary_env"]
