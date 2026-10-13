"""Reusable resource limits and consumable budgets for defensive processing."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
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
    max_steps: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_bytes", "max_items", "max_depth", "max_steps"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.timeout is not None:
            if isinstance(self.timeout, bool) or not isinstance(
                self.timeout, (int, float)
            ):
                raise ValueError(
                    "timeout must be a finite non-negative number or None"
                )
            try:
                timeout_float = float(self.timeout)
            except OverflowError:
                #? An int too large to convert to float (e.g. 10**400) must
                #? surface as the documented ValueError, not leak an internal
                #? OverflowError.
                raise ValueError(
                    "timeout must be a finite non-negative number or None"
                ) from None
            if not math.isfinite(timeout_float) or self.timeout < 0:
                raise ValueError(
                    "timeout must be a finite non-negative number or None"
                )

    def check_bytes(self,
        size: int,
    ) -> None:
        """check_bytes() function.

        Parameters
        ----------
        size : int
            size parameter.
        """
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("size must be a non-negative integer")
        if self.max_bytes is not None and size > self.max_bytes:
            raise ValueError("byte limit exceeded")

    def check_items(self,
        count: int,
    ) -> None:
        """check_items() function.

        Parameters
        ----------
        count : int
            count parameter.
        """
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a non-negative integer")
        if self.max_items is not None and count > self.max_items:
            raise ValueError("item limit exceeded")

    def check_steps(self,
        count: int,
    ) -> None:
        """check_steps() function.

        Parameters
        ----------
        count : int
            count parameter.
        """
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a non-negative integer")
        if self.max_steps is not None and count > self.max_steps:
            raise ValueError("step limit exceeded")


class ResourceBudget:
    """Track cumulative bytes/items, nesting depth, execution steps, and a deadline.

    This mutable budget has a single owner; concurrent access requires external
    synchronization. Deadline checks are cooperative and cannot interrupt a
    running body. A step checks before entry and after a successful body; errors
    from the body propagate unchanged.
    """

    __slots__ = (
        "max_bytes",
        "max_items",
        "max_depth",
        "timeout",
        "max_steps",
        "bytes_used",
        "items_used",
        "steps_used",
        "_clock",
        "_deadline",
    )

    def __init__(self,
        *,
        max_bytes: int | None = None,
        max_items: int | None = None,
        max_depth: int | None = None,
        timeout: float | None = None,
        max_steps: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        limits = Limits(max_bytes, max_items, max_depth, timeout, max_steps)
        self.max_bytes = limits.max_bytes
        self.max_items = limits.max_items
        self.max_depth = limits.max_depth
        self.timeout = limits.timeout
        self.max_steps = limits.max_steps
        self.bytes_used = 0
        self.items_used = 0
        self.steps_used = 0
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
    def from_limits(cls,
        limits: Limits,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> ResourceBudget:
        """Create a fresh consumable budget from stateless limits.

        Parameters
        ----------
        limits : Limits
            limits parameter.
        clock : Callable[[], float]
            clock parameter.

        Returns
        -------
        ResourceBudget
            The result of the operation.
        """
        return cls(
            max_bytes=limits.max_bytes,
            max_items=limits.max_items,
            max_depth=limits.max_depth,
            timeout=limits.timeout,
            max_steps=limits.max_steps,
            clock=clock,
        )

    def consume_bytes(self,
        amount: int,
    ) -> int:
        """Consume bytes and return the new cumulative count.

        Parameters
        ----------
        amount : int
            amount parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer")
        candidate = self.bytes_used + amount
        if self.max_bytes is not None and candidate > self.max_bytes:
            raise BudgetExceededError("byte budget exceeded")
        self.bytes_used = candidate
        return candidate

    def consume_items(self,
        amount: int = 1,
    ) -> int:
        """Consume items and return the new cumulative count.

        Parameters
        ----------
        amount : int
            amount parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer")
        candidate = self.items_used + amount
        if self.max_items is not None and candidate > self.max_items:
            raise BudgetExceededError("item budget exceeded")
        self.items_used = candidate
        return candidate

    def consume_steps(self,
        amount: int = 1,
    ) -> int:
        """Consume execution steps and return the new cumulative count.

        Parameters
        ----------
        amount : int
            amount parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer")
        candidate = self.steps_used + amount
        if self.max_steps is not None and candidate > self.max_steps:
            raise BudgetExceededError("step budget exceeded")
        self.steps_used = candidate
        return candidate

    @contextmanager
    def step(self,
        amount: int = 1,
    ) -> Generator[None, None, None]:
        """Check the deadline and consume steps on entry and check again on success.

        The body is not interrupted on expiration. Its own exceptions propagate
        unchanged, without a post-body deadline check replacing them.

        Parameters
        ----------
        amount : int
            amount parameter.

        Returns
        -------
        Generator[None, None, None]
            The result of the operation.
        """
        self.check_deadline()
        self.consume_steps(amount)
        yield
        self.check_deadline()

    def check_depth(self,
        depth: int,
    ) -> None:
        """Reject a nesting depth beyond the configured maximum.

        Parameters
        ----------
        depth : int
            depth parameter.
        """
        if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
            raise ValueError("depth must be a non-negative integer")
        if self.max_depth is not None and depth > self.max_depth:
            raise BudgetExceededError("depth budget exceeded")

    def _clock_now(self) -> float:
        """_clock_now() function.

        Returns
        -------
        float
            The result of the operation.
        """
        value = self._clock()
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("clock must return a finite numeric timestamp")
        return float(value)

    def check_deadline(self) -> None:
        """Reject work at or after the configured monotonic deadline.

        No parameters and no return value.
        """
        if (
            self._deadline is not None
            and self._clock_now() >= self._deadline
        ):
            raise BudgetExceededError("time budget exceeded")

    @property
    def remaining_bytes(self) -> int | None:
        """Return remaining bytes or None when unbounded.

        Returns
        -------
        int | None
            The result of the operation.
        """
        if self.max_bytes is None:
            return None
        return self.max_bytes - self.bytes_used

    @property
    def remaining_items(self) -> int | None:
        """Return remaining items or None when unbounded.

        Returns
        -------
        int | None
            The result of the operation.
        """
        if self.max_items is None:
            return None
        return self.max_items - self.items_used

    @property
    def remaining_steps(self) -> int | None:
        """Return remaining steps or None when unbounded.

        Returns
        -------
        int | None
            The result of the operation.
        """
        if self.max_steps is None:
            return None
        return self.max_steps - self.steps_used

    @property
    def remaining_seconds(self) -> float | None:
        """Return non-negative time remaining or None when unbounded.

        Returns
        -------
        float | None
            The result of the operation.
        """
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - self._clock_now())


__all__ = ["BudgetExceededError", "Limits", "ResourceBudget"]
