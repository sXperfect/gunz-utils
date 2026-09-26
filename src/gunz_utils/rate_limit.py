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

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until the requested token amount is available."""
        if tokens <= 0 or tokens > self.capacity:
            raise ValueError("tokens must be positive and <= capacity")
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._updated
                self._tokens = min(
                    self.capacity,
                    self._tokens + elapsed * self.rate,
                )
                self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self.rate
            await asyncio.sleep(wait)

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


__all__ = ["AsyncRateLimiter"]
