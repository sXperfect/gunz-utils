"""Async lifecycle and cancellation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


async def cancel_and_wait(
    *tasks: asyncio.Task[object],
) -> None:
    """Cancel tasks and wait for their cleanup without leaking cancellation.

    Parameters
    ----------
    tasks : asyncio.Task[object]
        tasks parameter.
    """
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


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
        or timeout < 0
    ):
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    try:
        timeout_float = float(timeout)
    except OverflowError:
        #? An int too large to convert to float (e.g. 10**400) must surface
        #? as the documented ValueError, not leak an internal OverflowError.
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        ) from None
    if not math.isfinite(timeout_float):
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    async with asyncio.timeout(timeout_float):
        return await awaitable


__all__ = ["cancel_and_wait", "with_timeout"]
