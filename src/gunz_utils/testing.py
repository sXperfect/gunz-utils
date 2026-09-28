"""Small testing helpers with no test-framework dependency."""

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
    """Temporarily set or remove environment variables and restore them."""
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


def eventually(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> None:
    """Wait until a predicate succeeds or raise TimeoutError."""
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
        or isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not math.isfinite(float(interval))
        or interval <= 0
    ):
        raise ValueError(
            "timeout must be finite and non-negative and interval "
            "must be finite and positive"
        )
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("condition did not become true before timeout")
        time.sleep(interval)


async def eventually_async(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> None:
    """Poll an async predicate without blocking other tasks.

    Args:
        predicate: Async condition to check until it succeeds.
        timeout: Maximum polling duration in seconds.
        interval: Delay between unsuccessful checks in seconds.

    Raises:
        ValueError: If timeout is negative or interval is not positive.
        TimeoutError: If the condition remains false until the deadline.
    """
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
        or isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not math.isfinite(float(interval))
        or interval <= 0
    ):
        raise ValueError(
            "timeout must be finite and non-negative and interval "
            "must be finite and positive"
        )
    deadline = time.monotonic() + timeout
    while True:
        if await predicate():
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("condition did not become true before timeout")
        await asyncio.sleep(interval)


__all__ = ["eventually", "eventually_async", "temporary_env"]
