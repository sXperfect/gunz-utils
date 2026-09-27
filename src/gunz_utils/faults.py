"""Deterministic fault-injection helpers for robustness testing."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class InjectedFault(RuntimeError):
    """Failure raised by the default named fault injector."""


def _named_fault(
    name: str,
) -> BaseException:
    """Build the default exception for one named checkpoint."""
    return InjectedFault(f"Injected failure at {name}")


@dataclass
class FailAfter:
    """Callable that raises a configured exception after N successful calls."""

    successes: int
    exception_factory: Callable[[], BaseException]
    calls: int = 0

    def __post_init__(self) -> None:
        """Validate the success budget and exception factory."""
        if (
            isinstance(self.successes, bool)
            or not isinstance(self.successes, int)
            or self.successes < 0
        ):
            raise ValueError("successes must be a non-negative integer")
        if (
            isinstance(self.calls, bool)
            or not isinstance(self.calls, int)
            or self.calls < 0
        ):
            raise ValueError("calls must be a non-negative integer")
        if not callable(self.exception_factory):
            raise TypeError("exception_factory must be callable")

    def __call__(self) -> None:
        """Record one call and raise after the configured success budget."""
        self.calls += 1
        if self.calls > self.successes:
            error = self.exception_factory()
            if not isinstance(error, BaseException):
                raise TypeError(
                    "exception_factory must return a BaseException"
                )
            raise error


@dataclass
class FaultSequence:
    """Deterministic sequence of success/failure decisions."""

    failures: AbstractSet[int]
    calls: int = 0

    def __post_init__(self) -> None:
        """Freeze and validate one-based failure indices."""
        frozen = frozenset(self.failures)
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 1
            for index in frozen
        ):
            raise ValueError(
                "failures must contain positive one-based integer indices"
            )
        if (
            isinstance(self.calls, bool)
            or not isinstance(self.calls, int)
            or self.calls < 0
        ):
            raise ValueError("calls must be a non-negative integer")
        self.failures = frozen

    def check(
        self,
        exception_factory: Callable[[], BaseException],
    ) -> None:
        """Raise on configured one-based call indices."""
        if not callable(exception_factory):
            raise TypeError("exception_factory must be callable")
        self.calls += 1
        if self.calls in self.failures:
            error = exception_factory()
            if not isinstance(error, BaseException):
                raise TypeError(
                    "exception_factory must return a BaseException"
                )
            raise error


@dataclass(frozen=True)
class NamedFaultInjector:
    """Raise deterministic failures at named lifecycle checkpoints.

    Parameters
    ----------
    fail_at : frozenset[str]
        Checkpoint names that should fail.
    exception_factory : Callable[[str], BaseException], optional
        Factory receiving the checkpoint name. Defaults to InjectedFault.
    """

    fail_at: AbstractSet[str]
    exception_factory: Callable[[str], BaseException] = _named_fault

    def __post_init__(self) -> None:
        """Freeze and validate checkpoint configuration."""
        frozen = frozenset(self.fail_at)
        if any(
            not isinstance(name, str) or not name
            for name in frozen
        ):
            raise ValueError(
                "fail_at must contain non-empty string checkpoint names"
            )
        if not callable(self.exception_factory):
            raise TypeError("exception_factory must be callable")
        object.__setattr__(
            self,
            "fail_at",
            frozen,
        )

    def checkpoint(
        self,
        name: str,
    ) -> None:
        """Raise the configured failure when name is selected."""
        if not isinstance(name, str):
            raise TypeError("checkpoint name must be a string")
        if not name:
            raise ValueError("checkpoint name must not be empty")
        if name in self.fail_at:
            error = self.exception_factory(name)
            if not isinstance(error, BaseException):
                raise TypeError(
                    "exception_factory must return a BaseException"
                )
            raise error


__all__ = [
    "FailAfter",
    "FaultSequence",
    "InjectedFault",
    "NamedFaultInjector",
]
