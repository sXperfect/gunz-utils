"""Generic circuit-breaker and bulkhead resilience primitives."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when an open circuit rejects work."""


class AsyncCircuitBreaker:
    """Protect async dependencies from repeated failing calls."""

    def __init__(
        self,
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
            raise ValueError(
                "failure_threshold must be a positive integer"
            )
        if (
            isinstance(recovery_timeout, bool)
            or not isinstance(recovery_timeout, (int, float))
            or not math.isfinite(float(recovery_timeout))
            or recovery_timeout < 0
        ):
            raise ValueError(
                "recovery_timeout must be a finite non-negative number"
            )
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_predicate = failure_predicate
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Return the current breaker state."""
        if self._opened_at is None:
            return CircuitState.CLOSED
        if time.monotonic() - self._opened_at >= self.recovery_timeout:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Execute work when allowed and update breaker state from its result."""
        async with self._lock:
            state = self.state
            if state is CircuitState.OPEN:
                raise CircuitOpenError("circuit is open")
            if state is CircuitState.HALF_OPEN:
                if self._half_open_in_flight:
                    raise CircuitOpenError("half-open probe already in flight")
                self._half_open_in_flight = True

        try:
            result = await operation()
        except asyncio.CancelledError:
            if state is CircuitState.HALF_OPEN:
                async with self._lock:
                    self._half_open_in_flight = False
            raise
        except Exception as exc:
            if self.failure_predicate is not None and not self.failure_predicate(exc):
                async with self._lock:
                    self._half_open_in_flight = False
                raise
            async with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._opened_at = time.monotonic()
                self._half_open_in_flight = False
            raise
        else:
            async with self._lock:
                self._failures = 0
                self._opened_at = None
                self._half_open_in_flight = False
            return result


class AsyncBulkhead:
    """Limit concurrent work for one dependency or resource class."""

    def __init__(self, limit: int) -> None:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
        ):
            raise ValueError("limit must be a positive integer")
        self.limit = limit
        self._semaphore = asyncio.Semaphore(limit)
        self._active = 0

    @property
    def available(self) -> int:
        """Return the currently available permit estimate."""
        return self.limit - self._active

    async def run(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        timeout: float | None = None,
    ) -> T:
        """Execute one operation after bounded permit acquisition."""
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or timeout < 0
        ):
            raise ValueError(
                "timeout must be a finite non-negative number or None"
            )
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
