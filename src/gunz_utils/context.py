"""Dependency-free operation context and correlation identifiers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar(
    "gunz_utils_correlation_id",
    default=None,
)


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
        raise TypeError(
            f"value must be a string or None, got {type(value).__name__}"
        )
    if value is None or not value.strip():
        correlation = str(uuid.uuid4())
    else:
        correlation = value
    token: Token[str | None] = _correlation_id.set(correlation)
    try:
        yield correlation
    finally:
        _correlation_id.reset(token)


__all__ = ["correlation_id", "ensure_correlation_id", "operation_context"]
