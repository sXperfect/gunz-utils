"""Deterministic fault-injection helpers for robustness testing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import BinaryIO, TypeVar

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


class VirtualClock:
    """Deterministic controllable monotonic clock for resilience testing."""

    def __init__(self, start_time: float = 1000.0) -> None:
        if (
            isinstance(start_time, bool)
            or not isinstance(start_time, (int, float))
            or start_time < 0
        ):
            raise ValueError("start_time must be a non-negative number")
        self._current: float = float(start_time)

    def now(self) -> float:
        """Return current virtual time in seconds."""
        return self._current

    def now_ns(self) -> int:
        """Return current virtual time in nanoseconds."""
        return int(self._current * 1e9)

    def advance(self, seconds: float) -> float:
        """Advance the virtual clock by seconds."""
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or seconds < 0
        ):
            raise ValueError("seconds must be a non-negative number")
        self._current += float(seconds)
        return self._current


class FaultyStream:
    """Binary stream wrapper that injects short writes or I/O faults."""

    def __init__(
        self,
        wrapped: BinaryIO,
        *,
        max_read_bytes: int | None = None,
        max_write_bytes: int | None = None,
        fail_read_after: int | None = None,
        fail_write_after: int | None = None,
        read_error: Callable[[], BaseException] | None = None,
        write_error: Callable[[], BaseException] | None = None,
    ) -> None:
        self.wrapped = wrapped
        self.max_read_bytes = max_read_bytes
        self.max_write_bytes = max_write_bytes
        self.fail_read_after = fail_read_after
        self.fail_write_after = fail_write_after
        self.read_error = read_error or (
            lambda: OSError("Injected stream read error")
        )
        self.write_error = write_error or (
            lambda: OSError("Injected stream write error")
        )
        self.read_calls = 0
        self.write_calls = 0

    def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        if self.fail_read_after is not None and self.read_calls > self.fail_read_after:
            raise self.read_error()
        if self.max_read_bytes is not None and (size < 0 or size > self.max_read_bytes):
            size = self.max_read_bytes
        return self.wrapped.read(size)

    def write(self, data: bytes) -> int:
        self.write_calls += 1
        if (
            self.fail_write_after is not None
            and self.write_calls > self.fail_write_after
        ):
            raise self.write_error()
        to_write = data
        if self.max_write_bytes is not None and len(to_write) > self.max_write_bytes:
            to_write = to_write[: self.max_write_bytes]
        return self.wrapped.write(to_write)

    def flush(self) -> None:
        self.wrapped.flush()

    def close(self) -> None:
        self.wrapped.close()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self.wrapped.seek(offset, whence)

    def tell(self) -> int:
        return self.wrapped.tell()


class AwaitBoundaryChaos:
    """Cooperative await interceptor injecting cancellation or errors."""

    def __init__(
        self,
        *,
        cancel_at_step: int | None = None,
        fail_at_step: int | None = None,
        exception_factory: Callable[[], BaseException] | None = None,
    ) -> None:

        self.cancel_at_step = cancel_at_step
        self.fail_at_step = fail_at_step
        self.exception_factory = exception_factory or (
            lambda: InjectedFault("Injected await boundary fault")
        )
        self.step_count = 0

    async def step(self) -> None:
        """Cooperative checkpoint simulating an await boundary."""
        self.step_count += 1
        if self.cancel_at_step is not None and self.step_count == self.cancel_at_step:
            raise asyncio.CancelledError("Injected await cancellation")
        if self.fail_at_step is not None and self.step_count == self.fail_at_step:
            raise self.exception_factory()
        await asyncio.sleep(0)


__all__ = [
    "AwaitBoundaryChaos",
    "FailAfter",
    "FaultSequence",
    "FaultyStream",
    "InjectedFault",
    "NamedFaultInjector",
    "VirtualClock",
]

