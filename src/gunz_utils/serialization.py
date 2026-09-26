"""Deterministic JSON serialization helpers."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def to_jsonable(value: Any) -> Any:
    """Convert common Python objects into JSON-compatible values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        converted = [to_jsonable(item) for item in value]
        return sorted(converted, key=lambda item: repr(item))
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
