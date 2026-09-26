"""Generic circuit-breaker and bulkhead resilience primitives."""

from __future__ import annotations

import asyncio
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
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must be non-negative")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
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
            raise
        except Exception:
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
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self.limit = limit
        self._semaphore = asyncio.Semaphore(limit)\n        self._active = 0

    @property
    def available(self) -> int:
        """Return the currently available permit estimate."""
        return self.limit - self._active

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Execute one operation while holding a bulkhead permit."""
        async with self._semaphore:
            return await operation()


__all__ = [
    "AsyncBulkhead",
    "AsyncCircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
]
