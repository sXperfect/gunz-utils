"""Layered configuration helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .dict_utils import deep_merge


def merge_configs(
    *configs: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge configuration layers from lowest to highest precedence.

    Parameters
    ----------
    configs : Mapping[str, Any]
        configs parameter.

    Returns
    -------
    dict[str, Any]
        The result of the operation.
    """
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
    """Convert prefixed environment names into a nested config mapping.

    Parameters
    ----------
    environ : Mapping[str, str]
        environ parameter.
    prefix : str
        prefix parameter.
    separator : str
        separator parameter.

    Returns
    -------
    dict[str, Any]
        The result of the operation.
    """
    if not isinstance(prefix, str) or not prefix.strip("_"):
        raise ValueError("prefix must be a non-empty string")
    if not isinstance(separator, str) or not separator:
        raise ValueError("separator must be a non-empty string")
    out: dict[str, Any] = {}
    seen_leaves: set[tuple[str, ...]] = set()
    prefix_upper = prefix.upper().rstrip("_")
    #? Only a canonical underscore run (e.g. "_" or "__") is a legacy
    #? underscore boundary. A separator that merely starts with "_" (e.g.
    #? "_X_") must require the actual separator string in the key, not just a
    #? single leading underscore.
    underscore_boundary = set(separator) == {"_"}
    for name, value in environ.items():
        upper = name.upper()
        #? Only keys whose leading characters actually match the prefix are
        #? owned by this config.  Without this check, an unrelated key whose
        #? prefix-length head equals the prefix (e.g. "XAP_PORT" for
        #? prefix="APP") would be misattributed and its value injected here.
        if not upper.startswith(prefix_upper):
            continue
        rest = upper[len(prefix_upper):]
        if underscore_boundary:
            #? Legacy single-underscore and canonical separator boundaries both
            #? begin with "_"; require at least one and strip all leading
            #? underscores after the prefix so no leading-underscore segment
            #? survives.
            if not rest.startswith("_"):
                continue
            suffix = name[len(prefix_upper):].lstrip("_")
        else:
            #? Non-underscore separator (e.g. "::", ":", "."): the key must
            #? carry the exact separator immediately after the prefix.
            if not rest.startswith(separator):
                continue
            suffix = name[len(prefix_upper):][len(separator):]
        if not suffix:
            continue
        parts = [part.lower() for part in suffix.split(separator)]
        if any(not part for part in parts):
            raise ValueError(f"environment key {name!r} contains an empty path segment")
        cursor = out
        for part in parts[:-1]:
            existing = cursor.setdefault(part, {})
            if not isinstance(existing, dict):
                raise ValueError(
                    f"environment key {name!r} conflicts with a scalar configuration"
                )
            cursor = existing
        if isinstance(cursor.get(parts[-1]), dict):
            raise ValueError(
                f"environment key {name!r} conflicts with a nested configuration"
            )
        path = tuple(parts)
        if path in seen_leaves:
            raise ValueError(
                f"environment key {name!r} collides case-insensitively with "
                "another key for the same configuration path"
            )
        seen_leaves.add(path)
        cursor[parts[-1]] = value
    return out


__all__ = ["env_overrides", "merge_configs"]
