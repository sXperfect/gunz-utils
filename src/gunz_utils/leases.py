"""Backend-neutral renewable lease heartbeat coordination."""

from __future__ import annotations

import asyncio
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
    """Perform one renewal and require an explicit ownership decision."""
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
    """Renew forever until cancelled or ownership is lost."""
    if renew_immediately:
        await _renew_once(renew)

    while True:
        await asyncio.sleep(interval)
        await _renew_once(renew)


async def run_with_lease_heartbeat(
    operation: Callable[[], Awaitable[T]],
    renew: Callable[[], Awaitable[bool]],
    *,
    heartbeat_interval: float,
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
    heartbeat_interval : float
        Seconds between renewal attempts. Must be finite and positive.
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
        If heartbeat_interval is invalid.
    Exception
        Any exception raised by the operation or renewal callback.

    Notes
    -----
    When renewal fails before the operation completes, the operation task is
    cancelled and awaited before the lease failure is re-raised. When the
    operation completes, the heartbeat task is cancelled and awaited. This
    prevents orphan heartbeat tasks and stale work from continuing after lease
    ownership is lost.
    """
    import math

    if not callable(operation):
        raise TypeError("operation must be callable")
    if not callable(renew):
        raise TypeError("renew must be callable")
    if (
        isinstance(heartbeat_interval, bool)
        or not isinstance(heartbeat_interval, (int, float))
        or not math.isfinite(float(heartbeat_interval))
        or heartbeat_interval <= 0
    ):
        raise ValueError(
            "heartbeat_interval must be a finite positive number"
        )

    operation_task = asyncio.create_task(operation())
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(
            renew,
            interval=float(heartbeat_interval),
            renew_immediately=renew_immediately,
        )
    )

    try:
        done, _pending = await asyncio.wait(
            {operation_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Lease loss wins if both tasks become ready in the same event-loop
        # turn. A worker that no longer owns the lease must not publish success.
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
        for task in (operation_task, heartbeat_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(
            operation_task,
            heartbeat_task,
            return_exceptions=True,
        )


__all__ = [
    "LeaseLostError",
    "LeaseTiming",
    "run_with_lease_heartbeat",
]
