"""Reusable bounded data structures and stream algorithms."""
from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import copy
import heapq
import math
import typing as t  #? Community-standard alias for typing imports.
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence, Set
from dataclasses import dataclass
from types import MappingProxyType

T = t.TypeVar("T")
_BOOL_SENTINEL = object()


class RingBuffer(t.Generic[T]):
    """Fixed-capacity FIFO retaining the newest values."""

    def __init__(self,
        capacity: int,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        #? deque(maxlen=...) evicts the oldest item once the cap is reached.
        self._capacity = capacity
        self._data: deque[T] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        """Return the maximum buffer capacity."""
        return self._capacity

    def append(self,
        value: T,
    ) -> None:
        """Append a value, evicting the oldest once the capacity is reached.

        Parameters
        ----------
        value : T
            Value to append to the buffer.

        Returns
        -------
        None
        """
        self._data.append(value)

    def extend(self,
        values: Iterable[T],
    ) -> None:
        """Append multiple values, evicting older elements as needed."""
        self._data.extend(values)

    def clear(self) -> None:
        """Remove all elements from the buffer."""
        self._data.clear()

    def to_list(self) -> list[T]:
        """Return a copy of the buffer elements as a list from oldest to newest."""
        return list(self._data)

    def peek_oldest(self) -> T:
        """Return the oldest element without removing it.

        Raises
        ------
        IndexError
            If the buffer is empty.
        """
        if not self._data:
            raise IndexError("peek from empty RingBuffer")
        return self._data[0]

    def peek_newest(self) -> T:
        """Return the newest element without removing it.

        Raises
        ------
        IndexError
            If the buffer is empty.
        """
        if not self._data:
            raise IndexError("peek from empty RingBuffer")
        return self._data[-1]

    def __getitem__(self,
        index: int,
    ) -> T:
        return self._data[index]

    def __iter__(self,
    ) -> Iterator[T]:
        return iter(self._data)

    def __len__(self,
    ) -> int:
        return len(self._data)

    def __bool__(self,
    ) -> bool:
        return bool(self._data)

    def __eq__(self,
        other: object,
    ) -> bool:
        if isinstance(other, RingBuffer):
            return self._capacity == other._capacity and self._data == other._data
        return False

    def __repr__(self,
    ) -> str:
        return f"RingBuffer({list(self._data)!r}, capacity={self._capacity})"


def top_k(
    items: Iterable[T],
    k: int,
    *,
    key: Callable[[T], Any] | None = None,
) -> list[T]:
    """Return the largest k values without sorting the complete input.

    Parameters
    ----------
    items : Iterable[T]
        Values to select from.
    k : int
        Number of largest values to return.
    key : Callable[[T], Any] or None, optional
        Function of one argument used to extract a comparison key.

    Returns
    -------
    list[T]
        The k largest values in descending order.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative integer")
    if key is not None and not callable(key):
        raise TypeError("key must be callable or None")
    #? heapq.nlargest is O(n log k) and keeps a bounded heap instead of a
    #? full sort, which is the point of this helper.
    return list(heapq.nlargest(k, items, key=key))


def bottom_k(
    items: Iterable[T],
    k: int,
    *,
    key: Callable[[T], Any] | None = None,
) -> list[T]:
    """Return the smallest k values without sorting the complete input.

    Parameters
    ----------
    items : Iterable[T]
        Values to select from.
    k : int
        Number of smallest values to return.
    key : Callable[[T], Any] or None, optional
        Function of one argument used to extract a comparison key.

    Returns
    -------
    list[T]
        The k smallest values in ascending order.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative integer")
    if key is not None and not callable(key):
        raise TypeError("key must be callable or None")
    return list(heapq.nsmallest(k, items, key=key))


def stable_unique(
    items: Iterable[T],
) -> Iterator[T]:
    """Yield hashable values once while preserving first-seen order.

    Parameters
    ----------
    items : Iterable[T]
        Values to deduplicate; each must be hashable.

    Returns
    -------
    Iterator[T]
        Each distinct value in its first-seen position.
    """
    seen: set[object] = set()
    for item in items:
        marker = (_BOOL_SENTINEL, item) if isinstance(item, bool) else item
        if marker not in seen:
            seen.add(marker)
            yield item


__all__ = [
    "DeepDifference",
    "RingBuffer",
    "bottom_k",
    "deep_diff",
    "freeze_structure",
    "retain_priority_and_recent",
    "stable_unique",
    "top_k",
]


def retain_priority_and_recent(
    #? --- Input ---
    items: Iterable[T],
    *,
    #? --- Retention policy ---
    is_priority: Callable[[T], bool],
    max_recent: int | None,
) -> list[T]:
    """Retain every priority item plus only the newest ordinary items.

    Parameters
    ----------
    items : Iterable[T]
        Items in chronological or append order.
    is_priority : Callable[[T], bool]
        Predicate identifying items that must always be retained.
    max_recent : int | None
        Maximum number of non-priority items to retain. None disables pruning
        and zero retains no non-priority items.

    Returns
    -------
    list[T]
        Retained items in their original order.

    Raises
    ------
    ValueError
        If max_recent is negative.

    Notes
    -----
    This is useful for bounded telemetry and audit histories where failures or
    other priority records must never be discarded while routine records can be
    capped.
    """
    if not callable(is_priority):
        raise TypeError("is_priority must be callable")
    if max_recent is not None and (
        isinstance(max_recent, bool)
        or not isinstance(max_recent, int)
        or max_recent < 0
    ):
        raise ValueError("max_recent must be a non-negative integer or None")
    values = list(items)
    if max_recent is None:
        return values
    if max_recent == 0:
        return [item for item in values if is_priority(item)]

    #? Priority items are always kept; only the newest max_recent ordinary
    #? items survive, preserving their original order.
    priorities = [bool(is_priority(item)) for item in values]
    ordinary_indices = [
        index for index, priority in enumerate(priorities) if not priority
    ]
    keep_ordinary = set(ordinary_indices[-max_recent:] if max_recent else [])
    return [
        item
        for index, item in enumerate(values)
        if priorities[index] or index in keep_ordinary
    ]


@dataclass(frozen=True, slots=True)
class DeepDifference:
    """One structural or scalar mismatch between nested Python values.

    Attributes
    ----------
    path : str
        Stable dotted/indexed path to the mismatch.
    kind : {"missing_left", "missing_right", "type", "length", "value"}
        Mismatch category.
    left : Any
        Left-side value, or None when absent.
    right : Any
        Right-side value, or None when absent.
    """

    path: str
    kind: t.Literal[
        "missing_left",
        "missing_right",
        "type",
        "length",
        "value",
    ]
    left: t.Any
    right: t.Any


def deep_diff(
    #? --- Inputs ---
    left: t.Any,
    right: t.Any,
    *,
    #? --- Traversal control ---
    path: str = "",
    nan_equal: bool = False,
    max_depth: int | None = None,
) -> list[DeepDifference]:
    """Return ordered structural differences between nested Python values.

    Mappings, lists, and tuples are traversed depth-first using an explicit stack.
    Missing keys/items
    are distinguished from present values equal to None. Strings and bytes are
    treated as scalar leaves.

    Parameters
    ----------
    left : Any
        Baseline value.
    right : Any
        Candidate value.
    path : str, optional
        Root path prefix for nested reports.
    nan_equal : bool, default=False
        Whether float NaN values should be treated as equal.
    max_depth : int or None, optional
        Maximum recursion depth to traverse into containers.

    Returns
    -------
    list[DeepDifference]
        Differences in deterministic traversal order.
    """
    if max_depth is not None and (
        isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0
    ):
        raise ValueError("max_depth must be a non-negative integer or None")
    if left is right and (
        (nan_equal and isinstance(left, float) and math.isnan(left))
        or not isinstance(left, float)
        or not math.isnan(left)
    ):
        return []
    differences: list[DeepDifference] = []
    #? Track id pairs of already-visited containers to stop traversal on
    #? shared or cyclic substructure without an unbounded recursion.
    visited: set[tuple[int, int]] = set()
    pending: list[Iterator[tuple[t.Any, t.Any, str, int] | DeepDifference]] = [
        iter(((left, right, path, 0),))
    ]

    def child_path(
        parent: str,
        key: t.Any,
    ) -> str:
        """Build a dotted/indexed path segment for a child key.

        Parameters
        ----------
        parent : str
            Path of the containing value.
        key : Any
            Child key; string keys use dotted notation, others are indexed.

        Returns
        -------
        str
            Combined child path.
        """
        if isinstance(key, str):
            return f"{parent}.{key}" if parent else key
        return f"{parent}[{key!r}]" if parent else f"[{key!r}]"

    def walk(
        left_value: t.Any,
        right_value: t.Any,
        current: str,
        depth: int,
    ) -> None:
        """Record one pair and schedule its children for depth-first traversal.

        Parameters
        ----------
        left_value : Any
            Baseline value at the current path.
        right_value : Any
            Candidate value at the current path.
        current : str
            Path of the current values in the report.
        depth : int
            Current nesting depth.

        Returns
        -------
        None
        """
        if left_value is right_value and (
            (nan_equal and isinstance(left_value, float) and math.isnan(left_value))
            or not isinstance(left_value, float)
            or not math.isnan(left_value)
        ):
            return
        if nan_equal and isinstance(left_value, float) and isinstance(right_value, float):
            if math.isnan(left_value) and math.isnan(right_value):
                return
        pair = (id(left_value), id(right_value))
        if pair in visited:
            return

        #? Mappings are compared by their sorted key union so the report order
        #? is deterministic regardless of insertion order.
        if isinstance(left_value, Mapping) and isinstance(right_value, Mapping):
            if max_depth is not None and depth >= max_depth:
                if left_value != right_value:
                    differences.append(
                        DeepDifference(current, "value", left_value, right_value)
                    )
                return
            visited.add(pair)
            keys = sorted(
                set(left_value) | set(right_value),
                key=repr,
            )
            def mapping_children(
            ) -> Iterator[tuple[t.Any, t.Any, str, int] | DeepDifference]:
                for key in keys:
                    nested = child_path(current, key)
                    if key not in left_value:
                        yield DeepDifference(
                            nested, "missing_left", None, right_value[key]
                        )
                    elif key not in right_value:
                        yield DeepDifference(
                            nested, "missing_right", left_value[key], None
                        )
                    else:
                        yield left_value[key], right_value[key], nested, depth + 1

            pending.append(mapping_children())
            return

        #? Strings, bytes, bytearrays, and memoryviews are scalar leaves, not sequences.
        scalar_sequence_types = (str, bytes, bytearray, memoryview)
        left_sequence = isinstance(left_value, Sequence) and not isinstance(
            left_value, scalar_sequence_types
        )
        right_sequence = isinstance(right_value, Sequence) and not isinstance(
            right_value, scalar_sequence_types
        )
        if left_sequence or right_sequence:
            if type(left_value) is not type(right_value):
                differences.append(
                    DeepDifference(
                        current,
                        "type",
                        type(left_value).__name__,
                        type(right_value).__name__,
                    )
                )
                return
            if max_depth is not None and depth >= max_depth:
                if left_value != right_value:
                    differences.append(
                        DeepDifference(current, "value", left_value, right_value)
                    )
                return
            visited.add(pair)
            left_length = len(left_value)
            right_length = len(right_value)
            if left_length != right_length:
                differences.append(
                    DeepDifference(
                        current,
                        "length",
                        left_length,
                        right_length,
                    )
                )
            #? Compare the shared prefix, then report the trailing tail of the
            #? longer sequence as missing on the shorter side.
            def sequence_children(
            ) -> Iterator[tuple[t.Any, t.Any, str, int] | DeepDifference]:
                for index in range(max(left_length, right_length)):
                    nested = f"{current}[{index}]"
                    if index >= right_length:
                        yield DeepDifference(
                            nested, "missing_right", left_value[index], None
                        )
                    elif index >= left_length:
                        yield DeepDifference(
                            nested, "missing_left", None, right_value[index]
                        )
                    else:
                        yield left_value[index], right_value[index], nested, depth + 1

            pending.append(sequence_children())
            return

        if type(left_value) is not type(right_value):
            differences.append(
                DeepDifference(
                    current,
                    "type",
                    type(left_value).__name__,
                    type(right_value).__name__,
                )
            )
            return

        #? A failed equality (e.g. a buggy __eq__) is surfaced as a typed
        #? error carrying the path rather than silently swallowed.
        try:
            equal = bool(left_value == right_value)
        except Exception as exc:
            raise TypeError(f"leaf equality failed at {current or '<root>'}") from exc
        if not equal:
            differences.append(
                DeepDifference(
                    current,
                    "value",
                    left_value,
                    right_value,
                )
            )

    while pending:
        try:
            item = next(pending[-1])
        except StopIteration:
            pending.pop()
            continue
        if isinstance(item, DeepDifference):
            differences.append(item)
        else:
            walk(*item)
    return differences


def freeze_structure(
    value: t.Any,
) -> t.Any:
    """Recursively freeze standard Python containers.

    Mappings become read-only mapping proxies, lists/tuples become tuples, and
    sets become frozensets. Scalar/other leaf values are defensively deep-copied.
    Cyclic container graphs are rejected explicitly. Standard containers are
    processed iteratively; custom leaf/key deepcopy hooks retain their own
    recursion and execution behavior. Mapping keys are also copied, so
    identity-based keys must be retrieved using the copied keys in the result.

    Parameters
    ----------
    value : Any
        Value to freeze.

    Returns
    -------
    Any
        Structurally immutable copy for standard container types.

    Raises
    ------
    ValueError
        If a cycle is encountered in a supported container graph.
    """
    #? Postorder assembly avoids Python recursion for standard containers.
    #? Active IDs reject cycles while allowing separate copies of shared nodes.
    active: set[int] = set()
    pending: list[tuple[str, t.Any, int]] = [("visit", value, 0)]
    results: list[t.Any] = []
    while pending:
        action, item, count = pending.pop()
        if action == "key":
            if isinstance(item, (int, float, str, bytes, bool, type(None))):
                results.append(item)
            else:
                results.append(copy.deepcopy(item))
            continue
        if action != "visit":
            children = results[-count:] if count else []
            if count:
                del results[-count:]
            result: t.Any
            if action == "mapping":
                result = MappingProxyType(
                    dict(zip(children[::2], children[1::2], strict=True))
                )
            elif action == "sequence":
                result = tuple(children)
            else:
                try:
                    result = frozenset(children)
                except TypeError as exc:
                    raise TypeError("frozen set elements must be hashable") from exc
            active.remove(id(item))
            results.append(result)
            continue
        if isinstance(item, (Mapping, list, tuple, set, frozenset, Set)):
            identifier = id(item)
            if identifier in active:
                raise ValueError("cycle detected while freezing structure")
            active.add(identifier)
            if isinstance(item, Mapping):
                entries = list(item.items())
                pending.append(("mapping", item, 2 * len(entries)))
                for key, child in reversed(entries):
                    pending.append(("visit", child, 0))
                    pending.append(("key", key, 0))
            else:
                values = list(item)
                action = "sequence" if isinstance(item, (list, tuple)) else "set"
                pending.append((action, item, len(values)))
                for child in reversed(values):
                    pending.append(("visit", child, 0))
        elif isinstance(item, (int, float, str, bytes, bool, type(None))):
            results.append(item)
        else:
            results.append(copy.deepcopy(item))
    return results[0]
