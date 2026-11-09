"""General-purpose collection transformations."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
K = TypeVar("K")
_BOOL_SENTINEL = object()


def unique(
    items: Iterable[T],
    *,
    key: Callable[[T], K] | None = None,
) -> list[T]:
    """Return first occurrences while preserving input order.

    Parameters
    ----------
    items : Iterable[T]
        items parameter.
    key : Callable[[T], K] | None
        key parameter.

    Returns
    -------
    list[T]
        The result of the operation.
    """
    if key is not None and not callable(key):
        raise TypeError("key must be callable or None")
    seen: set[object] = set()
    seen_unhashable: list[object] = []
    out: list[T] = []
    for item in items:
        marker: object = item if key is None else key(item)
        marker_key = (_BOOL_SENTINEL, marker) if isinstance(marker, bool) else marker
        try:
            if marker_key in seen:
                continue
            seen.add(marker_key)
        except TypeError:
            if any(marker == previous for previous in seen_unhashable):
                continue
            seen_unhashable.append(marker)
        out.append(item)
    return out


def group_by(
    items: Iterable[T],
    key: Callable[[T], K],
) -> dict[K, list[T]]:
    """Group items by a derived key while preserving item order.

    Parameters
    ----------
    items : Iterable[T]
        items parameter.
    key : Callable[[T], K]
        key parameter.

    Returns
    -------
    dict[K, list[T]]
        The result of the operation.
    """
    if not callable(key):
        raise TypeError("key must be callable")
    out: dict[K, list[T]] = {}
    for item in items:
        out.setdefault(key(item), []).append(item)
    return out


def index_by(
    items: Iterable[T],
    key: Callable[[T], K],
    *,
    strict: bool = False,
) -> dict[K, T]:
    """Index items by key; later items replace earlier duplicate keys.

    Parameters
    ----------
    items : Iterable[T]
        items parameter.
    key : Callable[[T], K]
        key parameter.
    strict : bool, default=False
        If True, raise ValueError on duplicate keys.

    Returns
    -------
    dict[K, T]
        The result of the operation.
    """
    if not callable(key):
        raise TypeError("key must be callable")
    out: dict[K, T] = {}
    for item in items:
        k = key(item)
        if strict and k in out:
            raise ValueError(f"duplicate key in index_by: {k!r}")
        out[k] = item
    return out


def partition(
    items: Iterable[T],
    predicate: Callable[[T], bool],
) -> tuple[list[T], list[T]]:
    """Split items into matching and non-matching lists.

    Parameters
    ----------
    items : Iterable[T]
        items parameter.
    predicate : Callable[[T], bool]
        predicate parameter.

    Returns
    -------
    tuple[list[T], list[T]]
        The result of the operation.
    """
    if not callable(predicate):
        raise TypeError("predicate must be callable")
    yes: list[T] = []
    no: list[T] = []
    for item in items:
        (yes if predicate(item) else no).append(item)
    return yes, no


__all__ = ["group_by", "index_by", "partition", "unique"]
