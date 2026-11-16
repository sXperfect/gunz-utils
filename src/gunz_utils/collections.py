"""General-purpose collection transformations."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, MutableSet
from typing import Any, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
_BOOL_SENTINEL = object()


class OrderedSet(MutableSet[T]):
    """Ordered set backed by dictionary keys."""

    def __init__(self,
        iterable: Iterable[T] | None = None,
    ) -> None:
        self._items: dict[T, None] = {}
        if iterable is not None:
            if isinstance(iterable, (str, bytes, bytearray)):
                raise TypeError("iterable must not be a string or bytes")
            for item in iterable:
                self._items[item] = None

    def __contains__(self,
        item: object,
    ) -> bool:
        return item in self._items

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def add(self,
        value: T,
    ) -> None:
        self._items[value] = None

    def discard(self,
        value: T,
    ) -> None:
        self._items.pop(value, None)

    def pop(self) -> T:
        if not self._items:
            raise KeyError("pop from an empty OrderedSet")
        key = next(reversed(self._items))
        del self._items[key]
        return key

    def __repr__(self) -> str:
        if not self._items:
            return f"{type(self).__name__}()"
        return f"{type(self).__name__}({list(self._items)})"


class FrozenDict(Mapping[K, V]):
    """Immutable hashable mapping."""

    def __init__(self,
        mapping: Mapping[K, V] | Iterable[tuple[K, V]] | None = None,
        **kwargs: V,
    ) -> None:
        data: dict[K, V] = {}
        if mapping is not None:
            if isinstance(mapping, Mapping):
                data.update(mapping)
            else:
                data.update(dict(mapping))
        if kwargs:
            data.update(kwargs)  # type: ignore[arg-type]
        self._data: dict[K, V] = dict(data)
        self._hash: int | None = None

    def __getitem__(self,
        key: K,
    ) -> V:
        return self._data[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._data!r})"

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(frozenset(self._data.items()))
        return self._hash

    def copy(self) -> FrozenDict[K, V]:
        return self


def chunked(
    iterable: Iterable[T],
    size: int,
) -> Iterator[list[T]]:
    """Yield successive chunks of length size from an iterable."""
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("size must be an integer")
    if size < 1:
        raise ValueError("size must be a positive integer")
    if isinstance(iterable, (str, bytes, bytearray)):
        raise TypeError("iterable must not be a string or bytes")
    chunk: list[T] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def flatten(
    iterable: Iterable[Any],
    *,
    depth: int | None = 1,
) -> Iterator[Any]:
    """Yield items from nested iterables up to the specified depth (default 1)."""
    if isinstance(iterable, (str, bytes, bytearray)):
        raise TypeError("iterable must not be a string or bytes")
    if depth is not None and (
    isinstance(
        depth,
        bool) or not isinstance(
            depth,
             int) or depth < 1):
        raise ValueError("depth must be a positive integer or None")

    for item in iterable:
        if isinstance(item, (str, bytes, bytearray)) or not isinstance(item, Iterable):
            yield item
        elif depth is None:
            yield from flatten(item, depth=None)
        elif depth > 1:
            yield from flatten(item, depth=depth - 1)
        else:
            yield from item


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
    if isinstance(items, (str, bytes, bytearray)):
        raise TypeError("items must not be a string or bytes")
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
    if isinstance(items, (str, bytes, bytearray)):
        raise TypeError("items must not be a string or bytes")
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
    if isinstance(items, (str, bytes, bytearray)):
        raise TypeError("items must not be a string or bytes")
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
    if isinstance(items, (str, bytes, bytearray)):
        raise TypeError("items must not be a string or bytes")
    if not callable(predicate):
        raise TypeError("predicate must be callable")
    yes: list[T] = []
    no: list[T] = []
    for item in items:
        (yes if predicate(item) else no).append(item)
    return yes, no


__all__ = [
    "FrozenDict",
    "OrderedSet",
    "chunked",
    "flatten",
    "group_by",
    "index_by",
    "partition",
    "unique",
]
