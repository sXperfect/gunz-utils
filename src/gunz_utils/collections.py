"""General-purpose collection transformations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
K = TypeVar("K")


def unique(items: Iterable[T], *, key: Callable[[T], K] | None = None) -> list[T]:
    """Return first occurrences while preserving input order."""
    seen: set[object] = set()
    out: list[T] = []
    for item in items:
        marker: object = item if key is None else key(item)
        try:
            if marker in seen:
                continue
            seen.add(marker)
        except TypeError:
            if any(marker == previous for previous in out):
                continue
        out.append(item)
    return out


def group_by(items: Iterable[T], key: Callable[[T], K]) -> dict[K, list[T]]:
    """Group items by a derived key while preserving item order."""
    out: dict[K, list[T]] = {}
    for item in items:
        out.setdefault(key(item), []).append(item)
    return out


def index_by(items: Iterable[T], key: Callable[[T], K]) -> dict[K, T]:
    """Index items by key; later items replace earlier duplicate keys."""
    return {key(item): item for item in items}


def partition(
    items: Iterable[T],
    predicate: Callable[[T], bool],
) -> tuple[list[T], list[T]]:
    """Split items into matching and non-matching lists."""
    yes: list[T] = []
    no: list[T] = []
    for item in items:
        (yes if predicate(item) else no).append(item)
    return yes, no


__all__ = ["group_by", "index_by", "partition", "unique"]
