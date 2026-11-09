"""Async lifecycle and cancellation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


async def cancel_and_wait(
    *tasks: asyncio.Future[object] | asyncio.Task[object],
) -> None:
    """Cancel tasks and wait for their cleanup without leaking cancellation.

    Parameters
    ----------
    tasks : asyncio.Future[object] | asyncio.Task[object]
        Futures or tasks to cancel and await.
    """
    for task in tasks:
        if not isinstance(task, (asyncio.Future, asyncio.Task)):
            raise TypeError(
                f"expected asyncio.Task or asyncio.Future, got {type(task).__name__}"
            )
        task.cancel()
    if tasks:
        drain = asyncio.gather(*tasks, return_exceptions=True)
        cancelled: asyncio.CancelledError | None = None
        while not drain.done():
            try:
                await asyncio.shield(drain)
            except asyncio.CancelledError as exc:
                cancelled = exc
        if cancelled is not None:
            raise cancelled


async def with_timeout(
    awaitable: Awaitable[T],
    timeout: float | None,
) -> T:
    """Await work with an optional timeout using asyncio.timeout.

    Parameters
    ----------
    awaitable : Awaitable[T]
        awaitable parameter.
    timeout : float | None
        timeout parameter.

    Returns
    -------
    T
        The result of the operation.
    """
    if timeout is None:
        return await awaitable
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        if inspect.iscoroutine(awaitable):
            awaitable.close()
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    async with asyncio.timeout(float(timeout)):
        return await awaitable


__all__ = ["cancel_and_wait", "with_timeout"]
