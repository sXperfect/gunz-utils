"""Safe conversion helpers for primitive configuration values.

These functions provide consistent, non-throwing parsing for callers that need
safe defaults, plus a strict boolean parser for validation boundaries.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = [
    "parse_bool",
    "parse_int_exact",
    "parse_key_value_pairs",
    "safe_bool",
    "safe_float",
    "safe_int",
    "safe_list",
]

_TRUE_STRINGS = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_STRINGS = frozenset({"0", "false", "f", "no", "n", "off"})


def _stripped(
    value: Any,
) -> Any:
    """Strip surrounding whitespace from strings, bytes, or bytearrays while preserving
    other types.

    Parameters
    ----------
    value : Any
        value parameter.

    Returns
    -------
    Any
        The result of the operation.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bytes, bytearray)):
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
    if isinstance(
    base, bool) or not isinstance(
        base, int) or not (
            base == 0 or 2 <= base <= 36):
        return default
    if min is not None and max is not None and min > max:
        return default
    stripped = _stripped(value)
    if isinstance(stripped, bool):
        return default
    try:
        if isinstance(stripped, (str, bytes, bytearray)):
            result = int(stripped, base)
        else:
            result = int(stripped)
    except (ValueError, TypeError, OverflowError):
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
    if min is not None and max is not None and min > max:
        return default
    stripped = _stripped(value)
    if isinstance(stripped, bool):
        return default
    try:
        result = float(stripped)
    except (ValueError, TypeError, OverflowError):
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
    if result == 0.0:
        result = 0.0
    return result


def safe_bool(
    value: Any,
    default: bool | None = None,
) -> bool | None:
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
    if isinstance(stripped, (bytes, bytearray)):
        try:
            stripped = stripped.decode("utf-8")
        except UnicodeDecodeError:
            return default
    if not isinstance(stripped, str):
        return default
    #? Case-insensitive canonical tokens make env/config values user-friendly.
    lowered = stripped.lower()
    if lowered in _TRUE_STRINGS:
        return True
    if lowered in _FALSE_STRINGS:
        return False
    return default


def parse_bool(
    value: Any,
) -> bool:
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
    raise ValueError(
        f"Cannot parse bool from type {type(value).__name__}; "
        f"expected one of {expected}"
    )


def parse_key_value_pairs(
    text: str,
    *,
    pair_delimiter: str = ",",
    kv_delimiter: str = "=",
) -> dict[str, str]:
    """Parse delimited key-value strings into a dictionary.

    Parameters
    ----------
    text : str
        String of key-value pairs (e.g. 'a=1, b=2').
    pair_delimiter : str, default=','
        Delimiter separating key-value pairs.
    kv_delimiter : str, default='='
        Delimiter separating keys and values.

    Returns
    -------
    dict[str, str]
        Parsed key-value mapping.

    Raises
    ------
    TypeError
        If text is not a string.
    ValueError
        If any pair is malformed (missing kv_delimiter).
    """
    if not isinstance(text, str):
        raise TypeError(f"expected str, got {type(text).__name__}")
    if not pair_delimiter or not kv_delimiter:
        raise ValueError("delimiters must not be empty")

    result: dict[str, str] = {}
    tokens = text.split(pair_delimiter)
    for token in tokens:
        stripped = token.strip()
        if not stripped:
            continue
        if kv_delimiter not in stripped:
            raise ValueError(
                f"malformed key-value pair missing {kv_delimiter!r}: {stripped!r}")
        key, val = stripped.split(kv_delimiter, 1)
        k = key.strip()
        v = val.strip()
        if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"')
               or (v[0] == "'" and v[-1] == "'")):
            v = v[1:-1]
        result[k] = v
    return result


def safe_list(
    value: Any,
) -> list[Any]:
    """Coerce single item, None, or iterable into a list without splitting strings.

    Parameters
    ----------
    value : Any
        Value to coerce into a list.

    Returns
    -------
    list[Any]
        Coerced list.
    """
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        return [value]
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    if isinstance(value, Iterable) and not isinstance(value, (dict, type)):
        return list(value)
    return [value]


def parse_int_exact(
    value: Any,
) -> int:
    """Strictly parse an integer, rejecting booleans, floats, and non-integer
    representations.

    Parameters
    ----------
    value : Any
        Value to parse strictly as integer.

    Returns
    -------
    int
        Exact parsed integer.

    Raises
    ------
    TypeError
        If value is a bool, float, or unsupported type.
    ValueError
        If value string is not a valid exact integer.
    """
    if isinstance(value, bool):
        raise TypeError("cannot parse exact int from bool")
    if isinstance(value, float):
        raise TypeError("cannot parse exact int from float")
    if isinstance(value, int):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        s = value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value
        s = s.strip()
        if not s:
            raise ValueError("cannot parse exact int from empty string")
        check_s = s[1:] if s[0] in "+-" else s
        if not check_s.isdigit():
            raise ValueError(f"invalid exact integer: {value!r}")
        return int(s, 10)
    raise TypeError(f"expected int or string, got {type(value).__name__}")

