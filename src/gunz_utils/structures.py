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
import typing as t  #? Community-standard alias for typing imports.
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

T = t.TypeVar("T")


class RingBuffer(t.Generic[T]):
    """Fixed-capacity FIFO retaining the newest values."""

    def __init__(self,
        capacity: int,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        #? deque(maxlen=...) evicts the oldest item once the cap is reached.
        self._data: deque[T] = deque(maxlen=capacity)

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

    def __iter__(self,
    ) -> Iterator[T]:
        return iter(self._data)

    def __len__(self,
    ) -> int:
        return len(self._data)


def top_k(
    items: Iterable[T],
    k: int,
) -> list[T]:
    """Return the largest k values without sorting the complete input.

    Parameters
    ----------
    items : Iterable[T]
        Values to select from.
    k : int
        Number of largest values to return.

    Returns
    -------
    list[T]
        The k largest values in descending order.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative integer")
    #? heapq.nlargest is O(n log k) and keeps a bounded heap instead of a
    #? full sort, which is the point of this helper.
    item_seq: Iterable[t.Any] = items
    return list(heapq.nlargest(k, item_seq))


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
        #? Key booleans as ``(bool, item)`` so ``True`` stays distinct from
        #? ``1`` and ``False`` from ``0``, honoring the package's
        #? bool-is-subtype-of-int dedup contract.
        marker: object = (bool, item) if isinstance(item, bool) else item
        if marker not in seen:
            seen.add(marker)
            yield item


__all__ = [
    "DeepDifference",
    "RingBuffer",
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
    if max_recent is not None and (
        isinstance(max_recent, bool)
        or not isinstance(max_recent, int)
        or max_recent < 0
    ):
        raise ValueError("max_recent must be a non-negative integer or None")
    values = list(items)
    if max_recent is None:
        return values

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


@dataclass(frozen=True)
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

    Returns
    -------
    list[DeepDifference]
        Differences in deterministic traversal order.

    Notes
    -----
    Alias topology is not compared. Mapping order is deterministic for keys with
    stable, distinct representations; arbitrary custom repr methods are outside
    that guarantee. This helper targets configuration, manifest, and metadata
    structures. Leaf
    values should implement scalar boolean equality. Specialized array/tensor
    equality belongs in the owning numerical package.
    """
    differences: list[DeepDifference] = []
    #? Track (id(left), id(right)) pairs currently on the ancestor path so
    #? traversal stops only on actual cycles, not on shared non-cyclic
    #? substructure that legitimately appears at multiple paths and must be
    #? compared each time. Pairs are added when their children are pushed and
    #? removed when that subtree finishes.
    active: set[tuple[int, int]] = set()
    pending: list[
        tuple[
            tuple[int, int] | None,
            Iterator[tuple[t.Any, t.Any, str] | DeepDifference],
        ]
    ] = [(None, iter(((left, right, path),)))]

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

        Returns
        -------
        None
        """
        pair = (id(left_value), id(right_value))
        if pair in active:
            return

        #? Mappings are compared by their sorted key union so the report order
        #? is deterministic regardless of insertion order.
        if isinstance(left_value, Mapping) and isinstance(right_value, Mapping):
            active.add(pair)
            keys = sorted(
                set(left_value) | set(right_value),
                key=repr,
            )
            def mapping_children(
            ) -> Iterator[tuple[t.Any, t.Any, str] | DeepDifference]:
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
                        yield left_value[key], right_value[key], nested

            pending.append((pair, mapping_children()))
            return

        #? Strings, bytes, and bytearrays are scalar leaves, not sequences.
        scalar_sequence_types = (str, bytes, bytearray)
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
            active.add(pair)
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
            ) -> Iterator[tuple[t.Any, t.Any, str] | DeepDifference]:
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
                        yield left_value[index], right_value[index], nested

            pending.append((pair, sequence_children()))
            return

        #? Leaf values implement scalar boolean equality: numerically-equal
        #? values of different numeric types (1 vs 1.0, int vs Decimal) are
        #? equal and must not be reported. Only report a difference when
        #? equality is False. Container type distinctions (list vs tuple) are
        #? handled earlier in the sequence branch and remain strict.
        try:
            equal = bool(left_value == right_value)
        except Exception as exc:
            #? A failed equality (e.g. a buggy __eq__) is surfaced as a typed
            #? error carrying the path rather than silently swallowed.
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
        pair, iterator = pending[-1]
        try:
            item = next(iterator)
        except StopIteration:
            pending.pop()
            if pair is not None:
                active.discard(pair)
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
                result = frozenset(children)
            active.remove(id(item))
            results.append(result)
            continue
        if isinstance(item, Mapping | list | tuple | set | frozenset):
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
                action = "sequence" if isinstance(item, list | tuple) else "set"
                pending.append((action, item, len(values)))
                for child in reversed(values):
                    pending.append(("visit", child, 0))
        else:
            results.append(copy.deepcopy(item))
    return results[0]
