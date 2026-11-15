"""Hierarchical data diffing, patch application, and inversion for nested mappings and lists."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DiffOp(str, Enum):
    """Operation type for a single difference node."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class DiffEntry:
    """Represents a discrete path change between two data structures."""

    path: tuple[str | int, ...]
    op: DiffOp
    old_value: Any = None
    new_value: Any = None

    @property
    def path_str(self) -> str:
        """Return dot-delimited path representation."""
        return ".".join(str(p) for p in self.path)


def resolve_path(
    data: Any,
    path: tuple[str | int, ...],
) -> Any:
    """Traverse a nested structure along path. Raises KeyError/IndexError if missing."""
    curr = data
    for step in path:
        if isinstance(curr, Mapping):
            curr = curr[step]
        elif isinstance(curr, (list, tuple)) and isinstance(step, int):
            curr = curr[step]
        else:
            raise LookupError(f"cannot traverse {step!r} on {type(curr).__name__}")
    return curr


def set_path(
    data: Any,
    path: tuple[str | int, ...],
    value: Any,
) -> None:
    """Set a value in a nested structure along path, creating intermediate dicts as needed."""
    if not path:
        raise ValueError("path must not be empty")
    curr = data
    for step in path[:-1]:
        if isinstance(curr, dict):
            if step not in curr or not isinstance(curr[step], (dict, list)):
                curr[step] = {}
            curr = curr[step]
        elif isinstance(curr, list) and isinstance(step, int):
            curr = curr[step]
        else:
            raise LookupError(f"cannot set along {step!r} on {type(curr).__name__}")

    last = path[-1]
    if isinstance(curr, dict):
        curr[last] = value
    elif isinstance(curr, list) and isinstance(last, int):
        if last < len(curr):
            curr[last] = value
        elif last == len(curr):
            curr.append(value)
        else:
            raise IndexError(f"list index out of range: {last}")
    else:
        raise LookupError(f"cannot assign to {type(curr).__name__}")


def deep_diff(
    a: Any,
    b: Any,
    prefix: tuple[str | int, ...] = (),
) -> list[DiffEntry]:
    """Compute recursive diff entries between any two JSON-compatible data structures."""
    if a == b:
        return []

    #? Mapping vs Mapping
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        entries: list[DiffEntry] = []
        all_keys = sorted(set(a.keys()) | set(b.keys()), key=lambda k: str(k))
        for k in all_keys:
            key_path = prefix + (k,)
            if k not in a:
                entries.append(DiffEntry(key_path, DiffOp.ADDED, None, b[k]))
            elif k not in b:
                entries.append(DiffEntry(key_path, DiffOp.REMOVED, a[k], None))
            else:
                entries.extend(deep_diff(a[k], b[k], prefix=key_path))
        return entries

    #? Sequence vs Sequence (excluding str/bytes)
    if (
        isinstance(a, Sequence)
        and not isinstance(a, (str, bytes, bytearray))
        and isinstance(b, Sequence)
        and not isinstance(b, (str, bytes, bytearray))
    ):
        entries = []
        max_len = max(len(a), len(b))
        for idx in range(max_len):
            idx_path = prefix + (idx,)
            if idx >= len(a):
                entries.append(DiffEntry(idx_path, DiffOp.ADDED, None, b[idx]))
            elif idx >= len(b):
                entries.append(DiffEntry(idx_path, DiffOp.REMOVED, a[idx], None))
            else:
                entries.extend(deep_diff(a[idx], b[idx], prefix=idx_path))
        return entries

    #? Primitive mismatch or different types
    return [DiffEntry(prefix, DiffOp.MODIFIED, a, b)]


def diff_dicts(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
) -> list[DiffEntry]:
    """Compute deep diff specifically between two mappings."""
    return deep_diff(a, b)


def diff_lists(
    a: Sequence[Any],
    b: Sequence[Any],
) -> list[DiffEntry]:
    """Compute deep diff specifically between two sequences."""
    return deep_diff(a, b)


def has_changes(
    diffs: Sequence[DiffEntry],
) -> bool:
    """Return True if sequence contains any non-UNCHANGED diff entries."""
    return any(d.op != DiffOp.UNCHANGED for d in diffs)


def filter_diffs(
    diffs: Sequence[DiffEntry],
    operations: set[DiffOp],
) -> list[DiffEntry]:
    """Filter diff entries by matching operation types."""
    return [d for d in diffs if d.op in operations]


def invert_diff(
    diffs: Sequence[DiffEntry],
) -> list[DiffEntry]:
    """Invert diff entries to rollback from destination back to origin."""
    inverted: list[DiffEntry] = []
    for d in diffs:
        if d.op == DiffOp.ADDED:
            inverted.append(DiffEntry(d.path, DiffOp.REMOVED, d.new_value, None))
        elif d.op == DiffOp.REMOVED:
            inverted.append(DiffEntry(d.path, DiffOp.ADDED, None, d.old_value))
        elif d.op == DiffOp.MODIFIED:
            inverted.append(DiffEntry(d.path, DiffOp.MODIFIED, d.new_value, d.old_value))
        else:
            inverted.append(d)
    return inverted


def patch_dict(
    target: dict[str, Any],
    diffs: Sequence[DiffEntry],
) -> dict[str, Any]:
    """Apply diff entries onto a copy of target dictionary."""
    res = copy.deepcopy(target)
    for d in diffs:
        if d.op == DiffOp.ADDED:
            set_path(res, d.path, d.new_value)
        elif d.op == DiffOp.MODIFIED:
            set_path(res, d.path, d.new_value)
        elif d.op == DiffOp.REMOVED:
            if not d.path:
                continue
            parent = res
            for step in d.path[:-1]:
                if isinstance(parent, dict) and step in parent:
                    parent = parent[step]
                else:
                    break
            last = d.path[-1]
            if isinstance(parent, dict) and last in parent:
                del parent[last]
    return res


def format_diff_summary(
    diffs: Sequence[DiffEntry],
) -> str:
    """Format diff entries into a concise human-readable summary string."""
    lines: list[str] = []
    for d in diffs:
        path = d.path_str or "<root>"
        if d.op == DiffOp.ADDED:
            lines.append(f"+ {path}: {d.new_value!r}")
        elif d.op == DiffOp.REMOVED:
            lines.append(f"- {path}: {d.old_value!r}")
        elif d.op == DiffOp.MODIFIED:
            lines.append(f"~ {path}: {d.old_value!r} -> {d.new_value!r}")
    return "\n".join(lines)


__all__ = [
    "DiffEntry",
    "DiffOp",
    "deep_diff",
    "diff_dicts",
    "diff_lists",
    "filter_diffs",
    "format_diff_summary",
    "has_changes",
    "invert_diff",
    "patch_dict",
    "resolve_path",
    "set_path",
]
