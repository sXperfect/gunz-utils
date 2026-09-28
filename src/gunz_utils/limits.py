"""Reusable resource limits and consumable budgets for defensive processing."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass


class BudgetExceededError(ValueError):
    """Raised when a consumable resource budget is exceeded."""


@dataclass(frozen=True)
class Limits:
    """Stateless upper bounds for defensive parsing and processing."""

    max_bytes: int | None = None
    max_items: int | None = None
    max_depth: int | None = None
    timeout: float | None = None

    def __post_init__(self) -> None:
        for name in ("max_bytes", "max_items", "max_depth"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.timeout is not None and (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(float(self.timeout))
            or self.timeout < 0
        ):
            raise ValueError("timeout must be a finite non-negative number or None")

    def check_bytes(self, size: int) -> None:
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("size must be a non-negative integer")
        if self.max_bytes is not None and size > self.max_bytes:
            raise ValueError("byte limit exceeded")

    def check_items(self, count: int) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a non-negative integer")
        if self.max_items is not None and count > self.max_items:
            raise ValueError("item limit exceeded")


class ResourceBudget:
    """Track cumulative bytes/items, nesting depth, and a monotonic deadline."""

    __slots__ = (
        "max_bytes",
        "max_items",
        "max_depth",
        "timeout",
        "bytes_used",
        "items_used",
        "_clock",
        "_deadline",
    )

    def __init__(
        self,
        *,
        max_bytes: int | None = None,
        max_items: int | None = None,
        max_depth: int | None = None,
        timeout: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        limits = Limits(max_bytes, max_items, max_depth, timeout)
        self.max_bytes = limits.max_bytes
        self.max_items = limits.max_items
        self.max_depth = limits.max_depth
        self.timeout = limits.timeout
        self.bytes_used = 0
        self.items_used = 0
        self._clock = clock
        if timeout is None:
            self._deadline = None
        else:
            now = self._clock_now()
            deadline = now + timeout
            if not math.isfinite(deadline):
                raise OverflowError(
                    "resource budget deadline exceeds finite float range"
                )
            self._deadline = deadline

    @classmethod
    def from_limits(
        cls,
        limits: Limits,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> ResourceBudget:
        """Create a fresh consumable budget from stateless limits."""
        return cls(
            max_bytes=limits.max_bytes,
            max_items=limits.max_items,
            max_depth=limits.max_depth,
            timeout=limits.timeout,
            clock=clock,
        )

    def consume_bytes(self, amount: int) -> int:
        """Consume bytes and return the new cumulative count."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer")
        candidate = self.bytes_used + amount
        if self.max_bytes is not None and candidate > self.max_bytes:
            raise BudgetExceededError("byte budget exceeded")
        self.bytes_used = candidate
        return candidate

    def consume_items(self, amount: int = 1) -> int:
        """Consume items and return the new cumulative count."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer")
        candidate = self.items_used + amount
        if self.max_items is not None and candidate > self.max_items:
            raise BudgetExceededError("item budget exceeded")
        self.items_used = candidate
        return candidate

    def check_depth(self, depth: int) -> None:
        """Reject a nesting depth beyond the configured maximum."""
        if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
            raise ValueError("depth must be a non-negative integer")
        if self.max_depth is not None and depth > self.max_depth:
            raise BudgetExceededError("depth budget exceeded")

    def _clock_now(self) -> float:
        value = self._clock()
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("clock must return a finite numeric timestamp")
        return float(value)

    def check_deadline(self) -> None:
        """Reject work at or after the configured monotonic deadline."""
        if (
            self._deadline is not None
            and self._clock_now() >= self._deadline
        ):
            raise BudgetExceededError("time budget exceeded")

    @property
    def remaining_bytes(self) -> int | None:
        """Return remaining bytes or None when unbounded."""
        if self.max_bytes is None:
            return None
        return self.max_bytes - self.bytes_used

    @property
    def remaining_items(self) -> int | None:
        """Return remaining items or None when unbounded."""
        if self.max_items is None:
            return None
        return self.max_items - self.items_used

    @property
    def remaining_seconds(self) -> float | None:
        """Return non-negative time remaining or None when unbounded."""
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - self._clock_now())


__all__ = ["BudgetExceededError", "Limits", "ResourceBudget"]
