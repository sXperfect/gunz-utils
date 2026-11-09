"""Generic circuit-breaker and bulkhead resilience primitives."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from enum import StrEnum
import math
import time
from typing import Any, TypeVar

T = TypeVar("T")

_breaker_context: ContextVar[dict[int, tuple[bool, int]] | None] = ContextVar(
    "_breaker_context", default=None
)


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when an open circuit rejects work."""


class AsyncCircuitBreaker:
    """Protect async dependencies from repeated failing calls."""

    def __init__(self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        failure_predicate: Callable[[BaseException], bool] | None = None,
    ) -> None:
        if (
            isinstance(failure_threshold, bool)
            or not isinstance(failure_threshold, int)
            or failure_threshold < 1
        ):
            raise ValueError("failure_threshold must be a positive integer")
        if (
            isinstance(recovery_timeout, bool)
            or not isinstance(recovery_timeout, (int, float))
            or not math.isfinite(float(recovery_timeout))
            or recovery_timeout < 0
        ):
            raise ValueError("recovery_timeout must be finite and non-negative")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_predicate = failure_predicate
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open_in_flight = False
        self._generation = 0
        self._lock = asyncio.Lock()

    @property
    def failure_count(self) -> int:
        """Return the current consecutive failure count.

        Returns
        -------
        int
            The number of consecutive failures.
        """
        return self._failures

    @property
    def state(self) -> CircuitState:
        """Return the current breaker state.

        Returns
        -------
        CircuitState
            The result of the operation.
        """
        if self._opened_at is None:
            return CircuitState.CLOSED
        if time.monotonic() - self._opened_at >= self.recovery_timeout:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    async def reset(self) -> None:
        """Reset the breaker to closed state, clearing failure counts."""
        async with self._lock:
            self._failures = 0
            self._opened_at = None
            self._half_open_in_flight = False
            self._generation += 1

    async def __aenter__(self) -> AsyncCircuitBreaker:
        async with self._lock:
            state = self.state
            if state is CircuitState.OPEN:
                raise CircuitOpenError("circuit is open")
            if state is CircuitState.HALF_OPEN:
                if self._half_open_in_flight:
                    raise CircuitOpenError("half-open probe already in flight")
                self._half_open_in_flight = True
                is_half_open_probe = True
            else:
                is_half_open_probe = False
            admitted_generation = self._generation

        ctx = _breaker_context.get()
        new_ctx = dict(ctx) if ctx is not None else {}
        new_ctx[id(self)] = (is_half_open_probe, admitted_generation)
        _breaker_context.set(new_ctx)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        ctx = _breaker_context.get()
        token_val = ctx.pop(id(self), None) if ctx else None
        if token_val is None:
            return None
        is_half_open_probe, admitted_generation = token_val
        try:
            if exc_val is not None:
                if isinstance(
                    exc_val, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)
                ):
                    return None
                predicate_exc: Exception | None = None
                is_failure = True
                if self.failure_predicate is not None:
                    try:
                        is_failure = bool(self.failure_predicate(exc_val))
                    except Exception as p_exc:
                        predicate_exc = p_exc
                        is_failure = True

                async with self._lock:
                    if is_failure:
                        if is_half_open_probe:
                            self._failures += 1
                            self._opened_at = time.monotonic()
                            self._generation += 1
                        elif (
                            self._generation == admitted_generation
                            and self._opened_at is None
                        ):
                            self._failures += 1
                            if self._failures >= self.failure_threshold:
                                self._opened_at = time.monotonic()
                                self._generation += 1

                if predicate_exc is not None:
                    raise predicate_exc from exc_val
            else:
                async with self._lock:
                    if is_half_open_probe:
                        self._failures = 0
                        self._opened_at = None
                    elif (
                        self._generation == admitted_generation
                        and self._opened_at is None
                    ):
                        self._failures = 0
        finally:
            if is_half_open_probe:
                async with self._lock:
                    self._half_open_in_flight = False

    async def call(self,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute work when allowed and update breaker state from its result.

        Parameters
        ----------
        operation : Callable[[], Awaitable[T]]
            operation parameter.

        Returns
        -------
        T
            The result of the operation.
        """
        async with self:
            return await operation()


class AsyncBulkhead:
    """Limit concurrent work for one dependency or resource class."""

    def __init__(self,
        limit: int,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        self.limit = limit
        self._semaphore = asyncio.Semaphore(limit)
        self._active = 0

    @property
    def active_count(self) -> int:
        """Return the number of currently active operations.

        Returns
        -------
        int
            Number of active operations.
        """
        return self._active

    @property
    def available_slots(self) -> int:
        """Return the currently available permit count.

        Returns
        -------
        int
            Number of available permits.
        """
        return self.available

    @property
    def available(self) -> int:
        """Return the currently available permit estimate.

        Returns
        -------
        int
            The result of the operation.
        """
        return self.limit - self._active

    async def __aenter__(self) -> AsyncBulkhead:
        await self._semaphore.acquire()
        self._active += 1
        return self

    async def __aexit__(self, *args: object) -> None:
        self._active -= 1
        self._semaphore.release()

    async def run(self,
        operation: Callable[[], Awaitable[T]],
        *,
        timeout: float | None = None,
    ) -> T:
        """Execute one operation after bounded permit acquisition.

        Parameters
        ----------
        operation : Callable[[], Awaitable[T]]
            operation parameter.
        timeout : float | None
            timeout parameter.

        Returns
        -------
        T
            The result of the operation.
        """
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or timeout < 0
        ):
            raise ValueError("timeout must be a finite non-negative number or None")
        try:
            if timeout is None:
                await self._semaphore.acquire()
            else:
                await asyncio.wait_for(self._semaphore.acquire(), timeout)
        except TimeoutError:
            raise TimeoutError("bulkhead acquisition timed out") from None

        self._active += 1
        try:
            return await operation()
        finally:
            self._active -= 1
            self._semaphore.release()


__all__ = [
    "AsyncBulkhead",
    "AsyncCircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
]
