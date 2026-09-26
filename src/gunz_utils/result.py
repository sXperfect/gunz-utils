"""Explicit success/error result values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass(frozen=True)
class Result(Generic[T, E]):
    """A value containing exactly one success value or error."""

    value: T | None = None
    error: E | None = None
    _ok: bool = True

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        """Construct a successful result."""
        return cls(value=value, _ok=True)

    @classmethod
    def err(cls, error: E) -> Result[T, E]:
        """Construct a failed result."""
        return cls(error=error, _ok=False)

    @property
    def is_ok(self) -> bool:
        return self._ok

    @property
    def is_err(self) -> bool:
        return not self._ok

    def unwrap(self) -> T:
        """Return the value or raise RuntimeError for an error result."""
        if not self._ok:
            raise RuntimeError(f"cannot unwrap error result: {self.error!r}")
        return cast(T, self.value)

    def unwrap_or(self, default: T) -> T:
        """Return the success value or a caller-provided default."""
        return cast(T, self.value) if self._ok else default

    def map(self, func: Callable[[T], U]) -> Result[U, E]:
        """Transform a successful value while preserving errors."""
        if self._ok:
            return Result[U, E].ok(func(cast(T, self.value)))
        return Result[U, E].err(cast(E, self.error))

    def map_error(self, func: Callable[[E], U]) -> Result[T, U]:
        """Transform an error while preserving successful values."""
        if self._ok:
            return Result[T, U].ok(cast(T, self.value))
        return Result[T, U].err(func(cast(E, self.error)))


__all__ = ["Result"]
