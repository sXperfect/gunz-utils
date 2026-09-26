"""Layered configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .dict_utils import deep_merge


def merge_configs(*configs: Mapping[str, Any]) -> dict[str, Any]:
    """Merge configuration layers from lowest to highest precedence."""
    result: dict[str, Any] = {}
    for config in configs:
        result = deep_merge(result, config)
    return result


def env_overrides(
    environ: Mapping[str, str],
    *,
    prefix: str,
    separator: str = "__",
) -> dict[str, Any]:
    """Convert prefixed environment names into a nested config mapping."""
    out: dict[str, Any] = {}
    prefix_value = prefix.upper().rstrip("_") + "_"
    for name, value in environ.items():
        upper = name.upper()
        if not upper.startswith(prefix_value):
            continue
        suffix = name[len(prefix_value):]
        if not suffix:
            continue
        cursor = out
        parts = [part.lower() for part in suffix.split(separator)]
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return out


__all__ = ["env_overrides", "merge_configs"]
