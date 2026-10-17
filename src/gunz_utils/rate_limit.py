"""Async token-bucket rate limiting."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
import sys
import time


class AsyncRateLimiter:
    """Token-bucket limiter with bounded burst capacity."""

    def __init__(self,
        rate: float,
        *,
        capacity: float | None = None,
    ) -> None:
        self.rate = self._finite_positive(rate, name="rate")
        raw_capacity = max(1.0, self.rate) if capacity is None else capacity
        self.capacity = self._finite_positive(raw_capacity, name="capacity")
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def available_tokens(self) -> float:
        """Return the estimated token balance without waiting.

        Returns
        -------
        float
            The result of the operation.
        """
        elapsed = time.monotonic() - self._updated
        try:
            tokens = self._tokens + elapsed * self.rate
        except OverflowError:
            tokens = self.capacity
        return min(self.capacity, tokens)

    #? GS046 false positive: 'tokens' parameter is token-bucket capacity,
    #? not an authentication credential or secret token.
    async def try_acquire(self,  # gunz-style: ignore[GS046]
        tokens: float = 1.0,
    ) -> bool:
        """Consume tokens immediately when available without waiting.

        Parameters
        ----------
        tokens : float
            tokens parameter.

        Returns
        -------
        bool
            The result of the operation.
        """
        tokens = self._validate_tokens(tokens)
        async with self._lock:
            self._refill()
            if self._tokens < tokens:
                return False
            self._tokens -= tokens
            return True

    #? GS046 false positive: 'tokens' parameter is token-bucket capacity,
    #? not an authentication credential or secret token.
    async def acquire(self,  # gunz-style: ignore[GS046]
        tokens: float = 1.0,
        *,
        timeout: float | None = None,
    ) -> None:
        """Wait until tokens are available or the optional timeout expires.

        Parameters
        ----------
        tokens : float
            tokens parameter.
        timeout : float | None
            timeout parameter.
        """
        tokens = self._validate_tokens(tokens)
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 <= timeout <= sys.float_info.max
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
                deficit = tokens - self._tokens
                try:
                    wait = deficit / self.rate
                except OverflowError:
                    wait = float("inf")
            first_attempt = False
            if deadline is not None:
                budget = deadline - time.monotonic()
                if budget <= 0 or wait > budget or not math.isfinite(wait):
                    raise TimeoutError("rate-limit acquisition timed out")
            elif not math.isfinite(wait):
                raise OverflowError(
                    "calculated rate-limit wait duration is non-finite"
                )
            await asyncio.sleep(wait)

    @staticmethod
    def _finite_positive(
        value: float,
        *,
        name: str,
    ) -> float:
        """_finite_positive() function.

        Parameters
        ----------
        value : float
            value parameter.
        name : str
            name parameter.

        Returns
        -------
        float
            The result of the operation.
        """
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < value <= sys.float_info.max
        ):
            raise ValueError(f"{name} must be a finite positive number")
        return float(value)

    def _validate_tokens(self,
        tokens: float,
    ) -> float:
        """_validate_tokens() function.

        Parameters
        ----------
        tokens : float
            tokens parameter.

        Returns
        -------
        float
            The result of the operation.
        """
        value = self._finite_positive(tokens, name="tokens")
        #? Check the original value before rounding a large integer to float.
        if tokens > self.capacity:
            raise ValueError("tokens must be positive and <= capacity")
        return value

    def _refill(self) -> None:
        """_refill() function.

        No parameters and no return value.
        """
        now = time.monotonic()
        elapsed = now - self._updated
        try:
            tokens = self._tokens + elapsed * self.rate
        except OverflowError:
            tokens = self.capacity
        self._tokens = min(self.capacity, tokens)
        self._updated = now

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self,
        *args: object,
    ) -> None:
        return None


__all__ = ["AsyncRateLimiter"]
