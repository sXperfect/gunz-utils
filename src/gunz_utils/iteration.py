"""Lazy iteration helpers for chunking, flattening, and single-element retrieval."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, TypeVar, cast

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "Clear BSD"
__version__ = "1.8.0"

__all__ = ["chunked", "batched", "flatten", "first"]

T = TypeVar("T")


def _take_n(it: Iterator[T], n: int) -> Iterator[T]:
    """Yield up to ``n`` items from ``it``, then stop. Internal helper."""
    for _ in range(n):
        try:
            yield next(it)
        except StopIteration:
            return


def chunked(iterable: Iterable[T], n: int) -> Iterator[tuple[T, ...]]:
    """Yield successive ``n``-sized tuples from ``iterable``.

    The final tuple may be shorter if the input length is not a multiple of
    ``n``. Tuples (not lists) are returned because callers frequently need
    immutable, hashable groups — for example as ``dict`` keys or ``set``
    elements.

    Parameters
    ----------
    iterable : Iterable[T]
        Source iterable. Consumed lazily — generators are supported.
    n : int
        Group size. Must be positive.

    Yields
    ------
    tuple[T, ...]
        Groups of up to ``n`` items.

    Raises
    ------
    ValueError
        If ``n`` is not positive.

    Examples
    --------
    >>> list(chunked([1, 2, 3, 4, 5], 2))
    [(1, 2), (3, 4), (5,)]
    >>> list(chunked([], 3))
    []
    >>> list(chunked(range(4), 2))
    [(0, 1), (2, 3)]
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    #? `iter()` accepts any iterable once; subsequent calls don't re-iterate,
    #? which is the desired lazy semantics. The `zip(..., strict=False)`
    #? default silently drops a partial final group — we want the partial
    #? group preserved, so build groups manually.
    it = iter(iterable)
    while True:
        group = tuple(_take_n(it, n))
        if not group:
            return
        yield group


def batched(iterable: Iterable[T], n: int) -> Iterator[list[T]]:
    """Yield successive ``n``-sized lists from ``iterable``.

    Like :func:`chunked` but returns mutable lists — useful when the caller
    intends to ``.append()`` or slice-assign into the group, or pass it to
    APIs that mutate the container.

    Parameters
    ----------
    iterable : Iterable[T]
        Source iterable. Consumed lazily — generators are supported.
    n : int
        Group size. Must be positive.

    Yields
    ------
    list[T]
        Groups of up to ``n`` items.

    Raises
    ------
    ValueError
        If ``n`` is not positive.

    Examples
    --------
    >>> list(batched([1, 2, 3, 4, 5], 2))
    [[1, 2], [3, 4], [5]]
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    #? Delegate to chunked and materialize each tuple into a fresh list —
    #? cheaper than re-implementing the loop, and the per-group copy is
    #? unavoidable for the mutable-list contract.
    for group in chunked(iterable, n):
        yield list(group)


def flatten(
    nested: Iterable,
    *,
    max_depth: int | None = None,
    types: tuple[type, ...] = (list, tuple),
) -> Iterator:
    """Recursively yield non-container items from a nested iterable.

    A generator that walks ``nested`` and yields every leaf. Containers
    matching ``types`` are descended into; everything else (dicts, sets,
    strings, scalars) is yielded as-is.

    Parameters
    ----------
    nested : Iterable
        Arbitrarily nested iterable. Strings are NOT descended into by
        default (the ``types`` tuple excludes ``str``).
    max_depth : int | None, optional
        Maximum number of container levels to flatten (Lodash semantics):
        ``None`` (default) flattens all levels; ``1`` flattens the
        outermost container only (nested containers are yielded as
        leaves); ``0`` yields each top-level element verbatim without
        descending at all.
    types : tuple[type, ...], optional
        Container types that should be descended into. Default is
        ``(list, tuple)``. Pass ``(list, tuple, set, frozenset)`` to also
        flatten set-valued nesting, etc.

    Yields
    ------
    Any
        Each non-container element found at the specified depth.

    Examples
    --------
    >>> list(flatten([[1, 2], [3, [4, 5]]]))
    [1, 2, 3, 4, 5]
    >>> list(flatten([[1, [2, [3]]]], max_depth=1))
    [1, [2, [3]]]
    >>> list(flatten([[1, [2, [3]]]], max_depth=2))
    [1, 2, [3]]
    >>> list(flatten((1, 2, 3)))
    [1, 2, 3]
    """
    if max_depth is not None and max_depth < 0:
        raise ValueError(f"max_depth must be non-negative, got {max_depth}")

    def _walk(item: Any, depth: int) -> Iterator:
        #? Strict `>` (rather than `>=`) gives Lodash-compatible semantics:
        #? max_depth=N means we may descend into up to N levels of
        #? containers. Items at depth > max_depth are yielded as leaves,
        #? whether they are scalars or containers.
        if max_depth is not None and depth > max_depth:
            yield item
            return
        if isinstance(item, types):
            #? isinstance narrows the runtime type but mypy can't infer it
            #? across a tuple of arbitrary container types; explicit cast.
            for sub in cast(Iterable[Any], item):
                yield from _walk(sub, depth + 1)
        else:
            yield item

    #? Top-level dispatch: iterate the outer Iterable (the type contract)
    #? and walk each yielded item at depth 1. This handles generators and
    #? other non-list/tuple iterables uniformly. Scalar input (which
    #? violates the type signature) is handled defensively by yielding it
    #? as a single leaf — preserves the historical single-scalar use case.
    try:
        iterator = iter(nested)
    except TypeError:
        yield nested
        return
    for item in iterator:
        yield from _walk(item, 1)


def first(iterable: Iterable[T], *, default: T | None = None) -> T | None:
    """Return the first item from ``iterable``, or ``default`` if empty.

    Follows the ``more_itertools.first`` convention. Note that ``None`` is
    also a valid item, so callers whose iterables may legitimately contain
    ``None`` should pass an explicit sentinel (e.g. ``default=_SENTINEL``).

    Parameters
    ----------
    iterable : Iterable[T]
        Source iterable. Consumed only until the first item.
    default : T | None, optional
        Returned when ``iterable`` is empty. Default is ``None``.

    Returns
    -------
    T | None
        First item, or ``default``.

    Examples
    --------
    >>> first([1, 2, 3])
    1
    >>> first([])
    >>> first([], default="missing")
    'missing'
    >>> first(iter([]), default=42)
    42
    """
    #? `next()` with a sentinel avoids the cost of `iter()` for the common
    #? case and handles the empty-input branch in one line.
    return next(iter(iterable), default)
