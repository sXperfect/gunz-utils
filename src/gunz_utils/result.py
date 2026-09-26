"""Explicit success/error result values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


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
        return self.value  # type: ignore[return-value]


__all__ = ["Result"]
