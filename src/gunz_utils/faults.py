"""Deterministic fault-injection helpers for robustness testing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class FailAfter:
    """Callable that raises a configured exception after N successful calls."""

    successes: int
    exception_factory: Callable[[], BaseException]
    calls: int = 0

    def __call__(self) -> None:
        self.calls += 1
        if self.calls > self.successes:
            raise self.exception_factory()


@dataclass
class FaultSequence:
    """Deterministic sequence of success/failure decisions."""

    failures: frozenset[int]
    calls: int = 0

    def check(self, exception_factory: Callable[[], BaseException]) -> None:
        self.calls += 1
        if self.calls in self.failures:
            raise exception_factory()


__all__ = ["FailAfter", "FaultSequence"]
