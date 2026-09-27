"""Reusable resource limits and consumable budgets for defensive processing."""

from __future__ import annotations

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
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.timeout is not None and self.timeout < 0:
            raise ValueError("timeout must be non-negative")

    def check_bytes(self, size: int) -> None:
        if self.max_bytes is not None and size > self.max_bytes:
            raise ValueError("byte limit exceeded")

    def check_items(self, count: int) -> None:
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
        self._deadline = None if timeout is None else clock() + timeout

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
        if amount < 0:
            raise ValueError("amount must be non-negative")
        candidate = self.bytes_used + amount
        if self.max_bytes is not None and candidate > self.max_bytes:
            raise BudgetExceededError("byte budget exceeded")
        self.bytes_used = candidate
        return candidate

    def consume_items(self, amount: int = 1) -> int:
        """Consume items and return the new cumulative count."""
        if amount < 0:
            raise ValueError("amount must be non-negative")
        candidate = self.items_used + amount
        if self.max_items is not None and candidate > self.max_items:
            raise BudgetExceededError("item budget exceeded")
        self.items_used = candidate
        return candidate

    def check_depth(self, depth: int) -> None:
        """Reject a nesting depth beyond the configured maximum."""
        if depth < 0:
            raise ValueError("depth must be non-negative")
        if self.max_depth is not None and depth > self.max_depth:
            raise BudgetExceededError("depth budget exceeded")

    def check_deadline(self) -> None:
        """Reject work at or after the configured monotonic deadline."""
        if self._deadline is not None and self._clock() >= self._deadline:
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
        return max(0.0, self._deadline - self._clock())


__all__ = ["BudgetExceededError", "Limits", "ResourceBudget"]
