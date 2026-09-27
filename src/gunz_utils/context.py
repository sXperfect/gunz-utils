"""Dependency-free operation context and correlation identifiers."""

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
    """Return the correlation identifier for the current execution context."""
    return _correlation_id.get()


def ensure_correlation_id() -> str:
    """Return the current identifier, creating one when absent."""
    current = _correlation_id.get()
    if current is not None:
        return current
    value = str(uuid.uuid4())
    _correlation_id.set(value)
    return value


@contextmanager
def operation_context(value: str | None = None) -> Iterator[str]:
    """Temporarily establish a correlation identifier for nested operations."""
    correlation = value or str(uuid.uuid4())
    token: Token[str | None] = _correlation_id.set(correlation)
    try:
        yield correlation
    finally:
        _correlation_id.reset(token)


__all__ = ["correlation_id", "ensure_correlation_id", "operation_context"]
