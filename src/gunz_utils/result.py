"""Explicit success/error result values."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")

#? Sentinel distinguishing "caller did not set _ok" from an explicit True, so
#? the constructor can infer the active variant from which field is populated.
_UNSET = object()


@dataclass(frozen=True)
class Result(Generic[T, E]):
    """A tagged success or error with no payload in the inactive variant.

    None is valid in either active variant; _ok identifies which is active.
    """

    value: T | None = None
    error: E | None = None
    _ok: bool | object = _UNSET

    def __post_init__(self) -> None:
        if self._ok is _UNSET:
            #? Infer the active variant from which field the caller populated,
            #? so ``Result(error=exc)`` builds an error result and
            #? ``Result(value=v)`` a success result.
            object.__setattr__(self, "_ok", self.error is None)
        if not isinstance(self._ok, bool):
            raise TypeError("_ok must be a boolean")
        if self._ok and self.error is not None:
            raise ValueError("successful result cannot contain an error")
        if not self._ok and self.value is not None:
            raise ValueError("error result cannot contain a success value")

    @classmethod
    def ok(cls,
        value: T,
    ) -> Result[T, E]:
        """Construct a successful result.

        Parameters
        ----------
        value : T
            value parameter.

        Returns
        -------
        Result[T, E]
            The result of the operation.
        """
        return cls(value=value, _ok=True)

    @classmethod
    def err(cls,
        error: E,
    ) -> Result[T, E]:
        """Construct a failed result.

        Parameters
        ----------
        error : E
            error parameter.

        Returns
        -------
        Result[T, E]
            The result of the operation.
        """
        return cls(error=error, _ok=False)

    @property
    def is_ok(self) -> bool:
        """is_ok() function.

        Returns
        -------
        bool
            The result of the operation.
        """
        return cast(bool, self._ok)

    @property
    def is_err(self) -> bool:
        """is_err() function.

        Returns
        -------
        bool
            The result of the operation.
        """
        return not self._ok

    def unwrap(self) -> T:
        """Return the value or raise RuntimeError for an error result.

        Returns
        -------
        T
            The result of the operation.
        """
        if not self._ok:
            raise RuntimeError(f"cannot unwrap error result: {self.error!r}")
        return cast(T, self.value)

    def unwrap_or(self,
        default: T,
    ) -> T:
        """Return the success value or a caller-provided default.

        Parameters
        ----------
        default : T
            default parameter.

        Returns
        -------
        T
            The result of the operation.
        """
        return cast(T, self.value) if self._ok else default

    def map(self,
        func: Callable[[T], U],
    ) -> Result[U, E]:
        """Transform a successful value while preserving errors.

        Parameters
        ----------
        func : Callable[[T], U]
            func parameter.

        Returns
        -------
        Result[U, E]
            The result of the operation.
        """
        if self._ok:
            return Result[U, E].ok(func(cast(T, self.value)))
        return Result[U, E].err(cast(E, self.error))

    def map_error(self,
        func: Callable[[E], U],
    ) -> Result[T, U]:
        """Transform an error while preserving successful values.

        Parameters
        ----------
        func : Callable[[E], U]
            func parameter.

        Returns
        -------
        Result[T, U]
            The result of the operation.
        """
        if self._ok:
            return Result[T, U].ok(cast(T, self.value))
        return Result[T, U].err(func(cast(E, self.error)))


__all__ = ["Result"]
