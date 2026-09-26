"""Typed environment-variable access."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
_MISSING = object()


def env(
    name: str,
    *,
    cast: Callable[[str], T] = str,
    default: T | object = _MISSING,
) -> T:
    """Read and convert an environment variable with explicit missing handling."""
    value = os.environ.get(name)
    if value is None:
        if default is _MISSING:
            raise KeyError(f"required environment variable {name!r} is not set")
        return default  # type: ignore[return-value]
    try:
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid value for environment variable {name!r}") from exc


def env_bool(name: str, *, default: bool | object = _MISSING) -> bool:
    """Read a strict boolean environment variable."""
    def parse(value: str) -> bool:
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError("expected boolean")

    return env(name, cast=parse, default=default)


__all__ = ["env", "env_bool"]
