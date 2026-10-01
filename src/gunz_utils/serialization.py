"""Deterministic JSON serialization helpers."""

from __future__ import annotations

import dataclasses
import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

try:
    _accel = importlib.import_module("._accel", package=__package__)
    _accel_is_json_clean: Callable[[Any, int], bool] | None = getattr(
        _accel, "is_json_clean", None
    )
except (ImportError, AttributeError):  # pragma: no cover
    _accel_is_json_clean = None


def to_jsonable(
    value: Any,
    *,
    _depth: int = 0,
    _max_depth: int = 100,
) -> Any:
    """Convert common Python objects into JSON-compatible values."""
    if _depth == 0 and _accel_is_json_clean is not None:
        if _accel_is_json_clean(value, _max_depth):
            return value

    # Security (VULN-2026-008): bound recursive traversal of attacker-shaped
    # objects before Python's own recursion limit can be exhausted.
    if _depth > _max_depth:
        raise ValueError(
            "object hierarchy exceeds maximum nesting depth "
            f"({_max_depth})"
        )

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
    if isinstance(value, (list, tuple)):
        return [
            to_jsonable(
                item,
                _depth=_depth + 1,
                _max_depth=_max_depth,
            )
            for item in value
        ]
    if isinstance(value, (set, frozenset)):
        items = [
            to_jsonable(
                item,
                _depth=_depth + 1,
                _max_depth=_max_depth,
            )
            for item in value
        ]
        return sorted(items, key=lambda item: repr(item))
    if isinstance(value, bytes):
        raise TypeError("bytes are not implicitly JSON serializable")
    return value


def json_dumps(value: Any, *, pretty: bool = False) -> str:
    """Serialize a value to stable UTF-8 JSON text."""
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


def json_loads(value: str | bytes | bytearray) -> Any:
    """Decode JSON text or bytes using the standard library decoder."""
    return json.loads(value)


def canonical_json(value: Any) -> str:
    """Return deterministic compact JSON suitable for hashes and cache keys."""
    return json_dumps(value)


__all__ = ["canonical_json", "json_dumps", "json_loads", "to_jsonable"]
