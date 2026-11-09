"""Typed environment-variable access."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar
from typing import cast as type_cast

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .parsing import safe_float, safe_int
from .sentinels import UNSET, UnsetType

T = TypeVar("T")


def env(
    name: str,
    *,
    cast: Callable[[str], T] | None = None,
    default: T | UnsetType = UNSET,
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
    if not isinstance(name, str) or not name:
        raise ValueError("environment variable name must be a non-empty string")
    value = os.environ.get(name)
    if value is None:
        if default is UNSET:
            raise KeyError(f"required environment variable {name!r} is not set")
        return type_cast(T, default)
    try:
        if cast is None:
            return type_cast(T, value)
        return cast(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid value for environment variable {name!r}") from None


def env_bool(
    name: str,
    *,
    default: bool | UnsetType = UNSET,
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


def env_int(
    name: str,
    *,
    default: int | UnsetType = UNSET,
    min: int | None = None,
    max: int | None = None,
) -> int:
    """Read a validated integer environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : int or UNSET
        Fallback when unset.
    min, max : int or None
        Inclusive bounds.

    Returns
    -------
    int
        Parsed integer.
    """
    if min is not None and max is not None and min > max:
        raise ValueError("min cannot be greater than max")

    def parse(val: str) -> int:
        parsed = safe_int(val, min=min, max=max)
        if parsed is None:
            raise ValueError(f"expected integer in bounds [{min}, {max}]")
        return parsed

    return env(name, cast=parse, default=default)


def env_float(
    name: str,
    *,
    default: float | UnsetType = UNSET,
    min: float | None = None,
    max: float | None = None,
    allow_inf: bool = False,
    allow_nan: bool = False,
) -> float:
    """Read a validated float environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : float or UNSET
        Fallback when unset.
    min, max : float or None
        Inclusive bounds.
    allow_inf, allow_nan : bool
        Whether inf or nan are accepted.

    Returns
    -------
    float
        Parsed float.
    """
    if min is not None and max is not None and min > max:
        raise ValueError("min cannot be greater than max")

    def parse(val: str) -> float:
        parsed = safe_float(
            val, min=min, max=max, allow_inf=allow_inf, allow_nan=allow_nan
        )
        if parsed is None:
            raise ValueError(f"expected float in bounds [{min}, {max}]")
        return parsed

    return env(name, cast=parse, default=default)


def env_list(
    name: str,
    *,
    separator: str = ",",
    strip: bool = True,
    default: list[str] | UnsetType = UNSET,
) -> list[str]:
    """Read a separated list of strings from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    separator : str
        Delimiter string.
    strip : bool
        Whether to strip whitespace from each element.
    default : list[str] or UNSET
        Fallback when unset.

    Returns
    -------
    list[str]
        List of parsed string tokens.
    """
    if not isinstance(separator, str) or not separator:
        raise ValueError("separator must be a non-empty string")

    def parse(val: str) -> list[str]:
        items = val.split(separator)
        if strip:
            items = [item.strip() for item in items]
        return items

    return env(name, cast=parse, default=default)


__all__ = ["env", "env_bool", "env_float", "env_int", "env_list"]
