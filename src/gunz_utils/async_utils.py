"""Async lifecycle and cancellation helpers."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


async def cancel_and_wait(*tasks: asyncio.Task[object]) -> None:
    """Cancel tasks and wait for their cleanup without leaking cancellation."""
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def with_timeout(awaitable: Awaitable[T], timeout: float | None) -> T:
    """Await work with an optional timeout using asyncio.timeout."""
    if timeout is None:
        return await awaitable
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    async with asyncio.timeout(float(timeout)):
        return await awaitable


__all__ = ["cancel_and_wait", "with_timeout"]
