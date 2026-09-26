"""Async token-bucket rate limiting."""

from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    """Token-bucket limiter with bounded burst capacity."""

    def __init__(self, rate: float, *, capacity: float | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
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
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative")
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self.rate
            if deadline is not None:
                budget = deadline - time.monotonic()
                if budget <= 0 or wait > budget:
                    raise TimeoutError("rate-limit acquisition timed out")
            await asyncio.sleep(wait)

    def _validate_tokens(self, tokens: float) -> None:
        if tokens <= 0 or tokens > self.capacity:
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
