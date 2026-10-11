"""Layered typed configuration values with provenance."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ConfigValue(Generic[T]):
    value: T
    source: str


def parse_bool(
    value: str,
) -> bool:
    """parse_bool() function.

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
    raise ValueError(f"invalid boolean: {value!r}")


def convert(
    value: str,
    parser: Callable[[str], T],
    *,
    source: str = "environment",
) -> ConfigValue[T]:
    """convert() function.

    Parameters
    ----------
    value : str
        value parameter.
    parser : Callable[[str], T]
        parser parameter.
    source : str
        source parameter.

    Returns
    -------
    ConfigValue[T]
        The result of the operation.
    """
    return ConfigValue(parser(value), source)


__all__ = ["ConfigValue", "convert", "parse_bool"]
