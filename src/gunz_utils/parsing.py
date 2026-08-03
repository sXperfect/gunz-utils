"""Safe conversion helpers for primitive configuration values.

These functions provide consistent, non-throwing parsing for callers that need
safe defaults, plus a strict boolean parser for validation boundaries.
"""

from __future__ import annotations

import math
from typing import Any

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "BSD 3-Clause"
__version__ = "1.6.0"

__all__ = ["safe_int", "safe_float", "safe_bool", "parse_bool"]

_TRUE_STRINGS = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_STRINGS = frozenset({"0", "false", "f", "no", "n", "off"})


def _stripped(value: Any) -> Any:
    """Strip surrounding whitespace from strings while preserving other types."""
    if isinstance(value, str):
        return value.strip()
    return value


def safe_int(
    value: Any,
    default: int | None = None,
    *,
    min: int | None = None,
    max: int | None = None,
    base: int = 10,
) -> int | None:
    """Parse an integer and return a fallback when parsing or bounds fail.

    Parameters
    ----------
    value : object
        Value accepted by :class:`int`, commonly a string or integer.
    default : int or None, optional
        Value returned when parsing fails or the result is out of bounds.
    min, max : int or None, optional
        Inclusive lower and upper bounds for the parsed value.
    base : int, optional
        Number base passed to :class:`int`.

    Returns
    -------
    int or None
        Parsed integer, or ``default`` on failure.
    """
    try:
        result = int(_stripped(value), base)
    except (ValueError, TypeError):
        return default
    if min is not None and result < min:
        return default
    if max is not None and result > max:
        return default
    return result


def safe_float(
    value: Any,
    default: float | None = None,
    *,
    min: float | None = None,
    max: float | None = None,
    allow_inf: bool = True,
    allow_nan: bool = False,
) -> float | None:
    """Parse a float and return a fallback when parsing or bounds fail.

    Parameters
    ----------
    value : object
        Value accepted by :class:`float`, commonly a string or numeric value.
    default : float or None, optional
        Value returned when parsing fails or the result is invalid.
    min, max : float or None, optional
        Inclusive lower and upper bounds for finite parsed values.
    allow_inf : bool, optional
        Whether positive and negative infinity are accepted. Defaults to true
        for compatibility with Python's normal float conversion.
    allow_nan : bool, optional
        Whether ``NaN`` is accepted. Defaults to false because it is unordered.

    Returns
    -------
    float or None
        Parsed float, or ``default`` on failure.
    """
    try:
        result = float(_stripped(value))
    except (ValueError, TypeError):
        return default
    #? Infinity remains opt-in controllable, while NaN stays rejected by default.
    if not allow_inf and math.isinf(result):
        return default
    if not allow_nan and math.isnan(result):
        return default
    if min is not None and result < min:
        return default
    if max is not None and result > max:
        return default
    return result


def safe_bool(value: Any, default: bool | None = None) -> bool | None:
    """Parse common boolean representations and return a fallback if unknown.

    Parameters
    ----------
    value : object
        Boolean, string, or other value to parse.
    default : bool or None, optional
        Value returned for unrecognized types and strings.

    Returns
    -------
    bool or None
        Parsed boolean, or ``default`` when the value is unrecognized.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    stripped = _stripped(value)
    if not isinstance(stripped, str):
        return default
    #? Case-insensitive canonical tokens make env/config values user-friendly.
    lowered = stripped.lower()
    if lowered in _TRUE_STRINGS:
        return True
    if lowered in _FALSE_STRINGS:
        return False
    return default


def parse_bool(value: Any) -> bool:
    """Parse a canonical boolean representation or raise ``ValueError``.

    Parameters
    ----------
    value : object
        Boolean, 0/1 integer, or canonical boolean string.

    Returns
    -------
    bool
        Parsed boolean value.

    Raises
    ------
    ValueError
        If ``value`` is not a recognized boolean representation.
    """
    result = safe_bool(value)
    if result is not None:
        return result
    expected = sorted(_TRUE_STRINGS | _FALSE_STRINGS)
    raise ValueError(f"Cannot parse bool from {value!r}; expected one of {expected}")
