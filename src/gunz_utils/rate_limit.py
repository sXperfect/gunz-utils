"""Async token-bucket rate limiting."""

from __future__ import annotations

import asyncio
import math
import time
from numbers import Real


def _finite_positive(name: str, value: Real) -> float:
    """Return a finite positive float or raise a stable validation error."""
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(float(value))
        or value <= 0
    ):
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def _finite_non_negative(name: str, value: Real) -> float:
    """Return a finite non-negative float or raise a stable validation error."""
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ValueError(
            f"{name} must be a finite non-negative number"
        )
    return float(value)


class AsyncRateLimiter:
    """Token-bucket limiter with bounded burst capacity."""

    def __init__(
        self,
        rate: float,
        *,
        capacity: float | None = None,
    ) -> None:
        self.rate = _finite_positive("rate", rate)
        self.capacity = _finite_positive(
            "capacity",
            self.rate if capacity is None else capacity,
        )
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def available_tokens(self) -> float:
        """Return the estimated token balance without waiting."""
        elapsed = time.monotonic() - self._updated
        return min(
            self.capacity,
            self._tokens + elapsed * self.rate,
        )

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """Consume tokens immediately when available without waiting."""
        requested = self._validate_tokens(tokens)
        async with self._lock:
            self._refill()
            if self._tokens < requested:
                return False
            self._tokens -= requested
            return True

    async def acquire(
        self,
        tokens: float = 1.0,
        *,
        timeout: float | None = None,
    ) -> None:
        """Wait until tokens are available or the optional timeout expires."""
        requested = self._validate_tokens(tokens)
        if timeout is not None:
            timeout = _finite_non_negative("timeout", timeout)
        deadline = (
            None
            if timeout is None
            else time.monotonic() + timeout
        )
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= requested:
                    self._tokens -= requested
                    return
                wait = (requested - self._tokens) / self.rate
            if deadline is not None:
                budget = deadline - time.monotonic()
                if budget <= 0 or wait > budget:
                    raise TimeoutError(
                        "rate-limit acquisition timed out"
                    )
            await asyncio.sleep(wait)

    def _validate_tokens(self, tokens: float) -> float:
        requested = _finite_positive("tokens", tokens)
        if requested > self.capacity:
            raise ValueError(
                "tokens must be <= capacity"
            )
        return requested

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated
        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.rate,
        )
        self._updated = now

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


__all__ = ["AsyncRateLimiter"]
