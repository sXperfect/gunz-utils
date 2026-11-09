"""Backend-neutral renewable lease heartbeat coordination."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class LeaseLostError(RuntimeError):
    """Raised when a lease renewal reports that ownership was lost."""


@dataclass(frozen=True, slots=True)
class LeaseTiming:
    """Validated lease duration and heartbeat cadence.

    Parameters
    ----------
    lease_seconds : float
        Lease duration granted by the backing scheduler/store.
    heartbeat_interval : float
        Renewal cadence. Must be strictly shorter than the lease duration.
    """

    lease_seconds: float
    heartbeat_interval: float

    def __post_init__(self) -> None:
        """Validate positive finite timing and a safe renewal cadence."""
        import math

        for name, value in (
            ("lease_seconds", self.lease_seconds),
            ("heartbeat_interval", self.heartbeat_interval),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value <= 0
            ):
                raise ValueError(
                    f"{name} must be a finite positive number"
                )

        if self.heartbeat_interval >= self.lease_seconds:
            raise ValueError(
                "heartbeat_interval must be shorter than lease_seconds"
            )


async def _renew_once(
    renew: Callable[[], Awaitable[bool]],
) -> None:
    """Perform one renewal and require an explicit ownership decision.

    Parameters
    ----------
    renew : Callable[[], Awaitable[bool]]
        renew parameter.
    """
    owned = await renew()
    if not isinstance(owned, bool):
        raise TypeError("renew callback must return bool")
    if not owned:
        raise LeaseLostError("lease ownership was lost")


async def _heartbeat_loop(
    renew: Callable[[], Awaitable[bool]],
    *,
    interval: float,
    renew_immediately: bool,
) -> None:
    """Renew forever until cancelled or ownership is lost.

    Parameters
    ----------
    renew : Callable[[], Awaitable[bool]]
        renew parameter.
    interval : float
        interval parameter.
    renew_immediately : bool
        renew_immediately parameter.
    """
    if renew_immediately:
        await _renew_once(renew)

    #? Heartbeat loop runs until the task is cancelled or ``_renew_once``
    #? raises ``LeaseLostError`` when ownership is lost, so it is not a
    #? non-terminating loop.
    while True:  # gunz-style: ignore[GS033]
        await asyncio.sleep(interval)
        await _renew_once(renew)


async def run_with_lease_heartbeat(
    operation: Callable[[], Awaitable[T]],
    renew: Callable[[], Awaitable[bool]],
    *,
    heartbeat_interval: float | None = None,
    timing: LeaseTiming | None = None,
    renew_immediately: bool = False,
) -> T:
    """Run async work while a renewable lease remains owned.

    Parameters
    ----------
    operation : Callable[[], Awaitable[T]]
        Work protected by the lease.
    renew : Callable[[], Awaitable[bool]]
        Renewal callback. Return True while the caller still owns the lease and
        False when ownership has been lost.
    heartbeat_interval : float | None, optional
        Seconds between renewal attempts. Must be finite and positive. Required
        unless timing is provided.
    timing : LeaseTiming | None, optional
        Validated lease timing configuration providing heartbeat_interval.
    renew_immediately : bool, optional
        Renew once before waiting for the first interval.

    Returns
    -------
    T
        Operation result when work completes before lease failure.

    Raises
    ------
    LeaseLostError
        If a renewal reports that ownership was lost.
    ValueError
        If heartbeat_interval is invalid or missing.
    TypeError
        If operation, renew, or timing is invalid.
    Exception
        Any exception raised by the operation or renewal callback.
    """
    if not callable(operation):
        raise TypeError("operation must be callable")
    if not callable(renew):
        raise TypeError("renew must be callable")
    if timing is not None:
        if not isinstance(timing, LeaseTiming):
            raise TypeError("timing must be a LeaseTiming instance or None")
        if heartbeat_interval is None:
            heartbeat_interval = timing.heartbeat_interval
    if heartbeat_interval is None:
        raise ValueError("heartbeat_interval or timing must be supplied")
    if not isinstance(renew_immediately, bool):
        raise ValueError("renew_immediately must be bool")
    if (
        isinstance(heartbeat_interval, bool)
        or not isinstance(heartbeat_interval, (int, float))
        or not math.isfinite(float(heartbeat_interval))
        or heartbeat_interval <= 0
    ):
        raise ValueError(
            "heartbeat_interval must be a finite positive number"
        )

    operation_task: asyncio.Future[T] | None = None
    heartbeat_task: asyncio.Task[None] | None = None
    try:
        op_awaitable = operation()
        try:
            operation_task = asyncio.ensure_future(op_awaitable)
        except BaseException:
            if inspect.iscoroutine(op_awaitable):
                op_awaitable.close()
            raise

        heartbeat_coroutine = _heartbeat_loop(
            renew,
            interval=float(heartbeat_interval),
            renew_immediately=renew_immediately,
        )
        try:
            heartbeat_task = asyncio.create_task(heartbeat_coroutine)
        except BaseException:
            heartbeat_coroutine.close()
            raise

        done, _pending = await asyncio.wait(
            {operation_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        #? Lease loss wins if both tasks become ready in the same event-loop
        #? turn. A worker that no longer owns the lease must not publish success.
        if heartbeat_task in done:
            heartbeat_error = heartbeat_task.exception()
            if not operation_task.done():
                operation_task.cancel()
            await asyncio.gather(
                operation_task,
                return_exceptions=True,
            )
            if heartbeat_error is None:
                raise LeaseLostError(
                    "lease heartbeat stopped unexpectedly"
                )
            raise heartbeat_error

        result = await operation_task
        heartbeat_task.cancel()
        await asyncio.gather(
            heartbeat_task,
            return_exceptions=True,
        )
        return result
    finally:
        tasks = [
            task
            for task in (operation_task, heartbeat_task)
            if task is not None
        ]
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            drain = asyncio.gather(
                *tasks,
                return_exceptions=True,
            )
            cancelled: asyncio.CancelledError | None = None
            while not drain.done():
                try:
                    await asyncio.shield(drain)
                except asyncio.CancelledError as exc:
                    cancelled = exc
            if cancelled is not None:
                raise cancelled


__all__ = [
    "LeaseLostError",
    "LeaseTiming",
    "run_with_lease_heartbeat",
]
