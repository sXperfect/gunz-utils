"""Dependency-free operation context and correlation identifiers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from types import MappingProxyType
from typing import Any

_correlation_id: ContextVar[str | None] = ContextVar(
    "gunz_utils_correlation_id",
    default=None,
)

_execution_context: ContextVar[Mapping[str, Any]] = ContextVar(
    "gunz_utils_execution_context",
    default=MappingProxyType({}),
)


def validate_correlation_id(
    value: str,
) -> bool:
    """Validate that correlation id is a non-empty string with safe characters."""
    if not isinstance(value, str):
        raise TypeError(f"correlation_id must be a string, got {type(value).__name__}")
    s = value.strip()
    if not s or len(s) > 128:
        raise ValueError("correlation_id must be non-empty and <= 128 characters")
    for ch in s:
        if not (ch.isalnum() or ch in "-_.:/"):
            raise ValueError(f"correlation_id contains invalid character: {ch!r}")
    return True


@contextmanager
def bind_context(
    **kwargs: Any,
) -> Iterator[dict[str, Any]]:
    """Temporarily bind key-value pairs into the current task's execution context."""
    current = dict(_execution_context.get())
    current.update(kwargs)
    token = _execution_context.set(current)
    try:
        yield current
    finally:
        _execution_context.reset(token)


def get_context(
    key: str | None = None,
    default: Any = None,
) -> Any:
    """Retrieve the entire execution context or a specific key within it."""
    ctx = _execution_context.get()
    if key is None:
        return dict(ctx)
    return ctx.get(key, default)


class ExecutionContext:
    """Read-only container of execution context data and correlation metadata."""

    def __init__(self,
        data: Mapping[str, Any] | None = None,
        correlation: str | None = None,
    ) -> None:
        self._data = dict(data) if data is not None else dict(_execution_context.get())
        self._correlation_id = (
            correlation if correlation is not None else correlation_id()
        )

    @property
    def correlation_id(self) -> str | None:
        """Current correlation identifier."""
        return self._correlation_id

    @property
    def data(self) -> dict[str, Any]:
        """Dictionary copy of context values."""
        return dict(self._data)

    def get(self,
        key: str,
        default: Any = None,
    ) -> Any:
        return self._data.get(key, default)

    def __getitem__(self,
        key: str,
    ) -> Any:
        return self._data[key]

    def __contains__(self,
        key: str,
    ) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return (f"ExecutionContext(correlation_id={self._correlation_id!r}, "
            f"data={self._data!r})")



def correlation_id() -> str | None:
    """Return the correlation identifier for the current execution context.

    Returns
    -------
    str | None
        The result of the operation.
    """
    return _correlation_id.get()


def ensure_correlation_id() -> str:
    """Return the current identifier, creating one when absent.

    Returns
    -------
    str
        The result of the operation.
    """
    current = _correlation_id.get()
    if current is not None:
        return current
    value = str(uuid.uuid4())
    _correlation_id.set(value)
    return value


def set_correlation_id(
    value: str | None,
) -> Token[str | None]:
    """Set the correlation identifier for the current execution context.

    Parameters
    ----------
    value : str | None
        Explicit correlation identifier or None to clear.

    Returns
    -------
    Token[str | None]
        Context variable reset token.
    """
    if value is not None and not isinstance(value, str):
        raise TypeError("correlation id must be a string or None")
    return _correlation_id.set(value)


def reset_correlation_id(
    token: Token[str | None],
) -> None:
    """Reset the correlation identifier to its previous state using a token.

    Parameters
    ----------
    token : Token[str | None]
        Token returned by set_correlation_id.
    """
    if not isinstance(token, Token):
        raise TypeError("token must be a contextvars.Token")
    _correlation_id.reset(token)


@contextmanager
def operation_context(
    value: str | None = None,
) -> Iterator[str]:
    """Temporarily establish a correlation identifier for nested operations.

    Parameters
    ----------
    value : str | None
        Explicit non-empty identifier. None or an empty string generates a UUID.

    Returns
    -------
    Iterator[str]
        The result of the operation.
    """
    if value is not None and not isinstance(value, str):
        raise TypeError("correlation id must be a string or None")
    correlation = value if (value is not None and value.strip()) else str(uuid.uuid4())
    token: Token[str | None] = _correlation_id.set(correlation)
    try:
        yield correlation
    finally:
        _correlation_id.reset(token)


__all__ = [
    "ExecutionContext",
    "bind_context",
    "correlation_id",
    "ensure_correlation_id",
    "get_context",
    "operation_context",
    "reset_correlation_id",
    "set_correlation_id",
    "validate_correlation_id",
]
