"""Async token-bucket rate limiting."""

from __future__ import annotations

import asyncio
import math
import time


class AsyncRateLimiter:
    """Token-bucket limiter with bounded burst capacity."""

    def __init__(self, rate: float, *, capacity: float | None = None) -> None:
        self.rate = self._finite_positive(rate, name="rate")
        raw_capacity = max(1.0, self.rate) if capacity is None else capacity
        self.capacity = self._finite_positive(raw_capacity, name="capacity")
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def available_tokens(self) -> float:
        """Return the estimated token balance without waiting."""
        elapsed = time.monotonic() - self._updated
        return min(self.capacity, self._tokens + elapsed * self.rate)

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """Consume tokens immediately when available without waiting."""
        self._validate_tokens(tokens)
        async with self._lock:
            self._refill()
            if self._tokens < tokens:
                return False
            self._tokens -= tokens
            return True

    async def acquire(
        self,
        tokens: float = 1.0,
        *,
        timeout: float | None = None,
    ) -> None:
        """Wait until tokens are available or the optional timeout expires."""
        self._validate_tokens(tokens)
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or timeout < 0
        ):
            raise ValueError("timeout must be a finite non-negative number or None")
        deadline = None if timeout is None else time.monotonic() + timeout
        first_attempt = True
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    if (
                        not first_attempt
                        and deadline is not None
                        and time.monotonic() > deadline
                    ):
                        raise TimeoutError("rate-limit acquisition timed out")
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self.rate
            first_attempt = False
            if deadline is not None:
                budget = deadline - time.monotonic()
                if budget <= 0 or wait > budget:
                    raise TimeoutError("rate-limit acquisition timed out")
            await asyncio.sleep(wait)

    @staticmethod
    def _finite_positive(value: float, *, name: str) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0
        ):
            raise ValueError(f"{name} must be a finite positive number")
        return float(value)

    def _validate_tokens(self, tokens: float) -> None:
        value = self._finite_positive(tokens, name="tokens")
        if value > self.capacity:
            raise ValueError("tokens must be positive and <= capacity")

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._updated
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._updated = now

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


__all__ = ["AsyncRateLimiter"]
