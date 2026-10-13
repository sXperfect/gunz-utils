"""Async lifecycle and cancellation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable
from typing import TypeVar, cast

T = TypeVar("T")

#? Upper bound on zero-delay drain ticks for a zero-timeout operation. It must
#? be generous enough for realistic ready-work (e.g. a gather of many ready
#? coroutines, each doing ``await asyncio.sleep(0)``) to settle, while still
#? bounding a pathological never-completing zero-delay coroutine so it fails
#? fast (raises ``TimeoutError``) instead of busy-spinning at 100% CPU.
_ZERO_TIMEOUT_MAX_DRAIN_TICKS = 1000


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
    if timeout_float == 0:
        return await _run_with_zero_timeout(awaitable)
    async with asyncio.timeout(timeout_float):
        return await awaitable


def _loop_needs_real_time(loop: asyncio.AbstractEventLoop) -> bool:
    """Whether the loop's soonest pending timer is strictly in the future.

    A zero-delay timer (e.g. ``asyncio.sleep(0)``) is scheduled for the
    current ``loop.time()``, so its deadline is not in the future. If the
    soonest remaining timer is strictly ahead of now, or there is none, then
    the only way for a pending task to make progress is real time (or an
    external event), so an already-settled task cannot complete without
    waiting. Used only to decide whether a zero-timeout operation must fail.
    """
    ready = getattr(loop, "_ready", None)
    if ready:
        return False
    scheduled = getattr(loop, "_scheduled", None)
    if not scheduled:
        return True
    soonest = scheduled[0]
    when = cast(float | None, getattr(soonest, "_when", None))
    if when is None:
        return True
    return when > loop.time()


async def _run_with_zero_timeout(awaitable: Awaitable[T]) -> T:
    """Run ``awaitable`` with a zero timeout ("do not wait").

    A zero timeout means succeed if the work is already ready. Both
    ``asyncio.timeout(0)`` and ``asyncio.wait_for(coro, 0)`` cancel any
    awaitable that yields even once, so an awaitable that needs no real time
    but schedules a tick (e.g. ``await asyncio.sleep(0)``) would be spuriously
    cancelled even though no waiting was required. Instead, give all zero-delay
    work a chance to settle and fail only when the awaitable actually blocks on
    real time.
    """
    task = asyncio.ensure_future(awaitable)
    loop = asyncio.get_running_loop()
    for _ in range(_ZERO_TIMEOUT_MAX_DRAIN_TICKS):
        if task.done():
            break
        await asyncio.sleep(0)
        if task.done() or _loop_needs_real_time(loop):
            break
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise TimeoutError
    return task.result()


__all__ = ["cancel_and_wait", "with_timeout"]
