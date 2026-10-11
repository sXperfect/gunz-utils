"""Typed environment-variable access."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar
from typing import cast as type_cast

T = TypeVar("T")
_MISSING = object()


def env(
    name: str,
    *,
    cast: Callable[[str], T] | None = None,
    default: T | object = _MISSING,
) -> T:
    """Read and convert an environment variable with explicit missing handling.

    Parameters
    ----------
    name : str
        name parameter.
    cast : Callable[[str], T] | None
        cast parameter.
    default : T | object
        default parameter.

    Returns
    -------
    T
        The result of the operation.
    """
    value = os.environ.get(name)
    if value is None:
        if default is _MISSING:
            raise KeyError(f"required environment variable {name!r} is not set")
        return type_cast(T, default)
    try:
        if cast is None:
            return type_cast(T, value)
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid value for environment variable {name!r}") from exc


def env_bool(
    name: str,
    *,
    default: bool | object = _MISSING,
) -> bool:
    """Read a strict boolean environment variable.

    Parameters
    ----------
    name : str
        name parameter.
    default : bool | object
        default parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
    def parse(
        value: str,
    ) -> bool:
        """parse() function.

        Parameters
        ----------
        value : str
            value parameter.

        Returns
        -------
        bool
            The result of the operation.
        """
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError("expected boolean")

    return env(name, cast=parse, default=default)


__all__ = ["env", "env_bool"]
