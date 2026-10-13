"""Deterministic JSON serialization helpers."""
from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import dataclasses
import importlib
import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
#? This core module has zero mandatory third-party runtime dependencies.

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
#? The optional native accelerator is loaded dynamically below to keep import
#? time side-effect free and the core package zero-dependency.
try:
    _accel = importlib.import_module("._accel", package=__package__)
    _accel_is_json_clean: Callable[[Any, int], bool] | None = getattr(
        _accel, "is_json_clean", None
    )
except (ImportError, AttributeError):  # pragma: no cover
    _accel_is_json_clean = None


_MAX_JSON_DEPTH = 100


def _excessive_nesting_position(
    text: str,
    max_depth: int,
) -> int:
    """Return the index where nesting exceeds ``max_depth``, else ``-1``.

    Scans the JSON text tracking bracket depth while skipping string literal
    contents, so ``[``/``{`` inside strings do not count toward nesting.
    """
    depth = 0
    in_string = False
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if in_string:
            if character == "\\":
                index += 2
                continue
            if character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            index += 1
            continue
        if character in "[{":
            depth += 1
            if depth > max_depth:
                return index
        elif character in "]}":
            depth = depth - 1 if depth else 0
        index += 1
    return -1


def to_jsonable(
    value: Any,
    *,
    _depth: int = 0,
    _max_depth: int = 100,
) -> Any:
    """Convert common Python objects into JSON-compatible values.

    When native acceleration is active and the input is already clean and
    JSON-compatible, the input object itself may be returned directly to avoid
    costly recursive re-allocation. Callers that require mutation isolation
    must explicitly deep-copy the object.

    Parameters
    ----------
    value : Any
        Object to convert.
    _depth : int, default=0
        Internal recursion depth counter.
    _max_depth : int, default=100
        Maximum allowed nesting depth before raising.

    Returns
    -------
    Any
        A JSON-compatible value, or the input unchanged when it already is.
    """
    #? Security (VULN-2026-008): bound recursive traversal of attacker-shaped
    #? objects before Python's own recursion limit can be exhausted.
    #? Validate with Python integer semantics before narrowing an optimization
    #? budget for the native classifier. Negative depths retain reference errors.
    if _depth > _max_depth:
        raise ValueError(
            "object hierarchy exceeds maximum nesting depth "
            f"({_max_depth})"
        )

    if _depth == 0 and _accel_is_json_clean is not None:
        #? Native traversal falls back beyond depth 128. The ceiling below only
        #? bounds its C-int argument; recursive normalization retains _max_depth.
        native_depth = (
            min(_max_depth, 129) if isinstance(_max_depth, int) else _max_depth
        )
        if _accel_is_json_clean(value, native_depth):
            return value

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_jsonable(
                getattr(value, field.name),
                _depth=_depth + 1,
                _max_depth=_max_depth,
            )
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key)
            if normalized in converted:
                raise ValueError(
                    "mapping keys collide after JSON key normalization: "
                    f"{normalized!r}"
                )
            converted[normalized] = to_jsonable(
                item,
                _depth=_depth + 1,
                _max_depth=_max_depth,
            )
        return converted
    if isinstance(value, list | tuple):
        return [
            to_jsonable(
                item,
                _depth=_depth + 1,
                _max_depth=_max_depth,
            )
            for item in value
        ]
    if isinstance(value, set | frozenset):
        items = [
            to_jsonable(
                item,
                _depth=_depth + 1,
                _max_depth=_max_depth,
            )
            for item in value
        ]
        #? Ordering must normalize mapping keys too: repr(dict) retains insertion
        #? order even though the final JSON encoder sorts those same keys.
        #? default=repr only forms a sort key for existing passthrough objects;
        #? the returned payload stays unchanged and canonical_json still rejects
        #? values unsupported by the actual JSON encoder.
        return sorted(
            items,
            key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, allow_nan=False,
                separators=(",", ":"), default=repr,
            ),
        )
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError("bytes are not implicitly JSON serializable")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValueError("Out of range float values are not JSON compliant")
    return value


def json_dumps(
    value: Any,
    *,
    pretty: bool = False,
) -> str:
    """Serialize a value to stable UTF-8 JSON text.

    Parameters
    ----------
    value : Any
        Value to serialize.
    pretty : bool, default=False
        Pretty-print with two-space indentation instead of compact output.

    Returns
    -------
    str
        Stable UTF-8 JSON text.
    """
    kwargs: dict[str, Any] = {
        "ensure_ascii": False,
        "sort_keys": True,
        "allow_nan": False,
    }
    if pretty:
        kwargs.update(indent=2)
    else:
        kwargs.update(separators=(",", ":"))
    return json.dumps(to_jsonable(value), **kwargs)


def json_loads(
    value: str | bytes | bytearray,
) -> Any:
    """Decode JSON text or bytes using the standard library decoder.

    Nesting depth is bounded to mirror the encode-side recursion limit, so a
    pathologically nested document raises :class:`json.JSONDecodeError` (a
    ``ValueError``) rather than an uncontrolled ``RecursionError``.

    Parameters
    ----------
    value : str | bytes | bytearray
        JSON-encoded text or bytes to decode.

    Returns
    -------
    Any
        The decoded Python object.
    """
    if isinstance(value, bytes | bytearray):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
    else:
        text = value
    position = _excessive_nesting_position(text, _MAX_JSON_DEPTH)
    if position >= 0:
        raise json.JSONDecodeError(
            f"JSON document is nested deeper than {_MAX_JSON_DEPTH} levels",
            text,
            position,
        )
    return json.loads(value)


def canonical_json(
    value: Any,
) -> str:
    """Return deterministic compact JSON suitable for hashes and cache keys.

    Parameters
    ----------
    value : Any
        Value to serialize.

    Returns
    -------
    str
        Deterministic compact JSON text.
    """
    return json_dumps(value)


__all__ = ["canonical_json", "json_dumps", "json_loads", "to_jsonable"]
