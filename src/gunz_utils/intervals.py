"""Range queries and interval trees for efficient 1D overlap detection."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Interval(Generic[T]):
    """1D interval [start, end) with optional associated payload."""

    start: float
    end: float
    data: T | None = None

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(
                f"interval start ({self.start}) cannot exceed end ({self.end})")

    @property
    def length(self) -> float:
        """Return the span length of the interval."""
        return self.end - self.start

    def overlaps(self,
        other: Interval[Any],
    ) -> bool:
        """Return True if this interval overlaps with other."""
        return self.start < other.end and other.start < self.end

    def contains_point(self,
        point: float,
    ) -> bool:
        """Return True if point falls within [start, end)."""
        return self.start <= point < self.end


class _IntervalNode(Generic[T]):
    __slots__ = ("interval", "left", "max_end", "right")

    def __init__(self,
        interval: Interval[T],
    ) -> None:
        self.interval = interval
        self.max_end = interval.end
        self.left: _IntervalNode[T] | None = None
        self.right: _IntervalNode[T] | None = None


class IntervalTree(Generic[T]):
    """Augmented binary search tree for fast interval intersection queries."""

    def __init__(self) -> None:
        self._root: _IntervalNode[T] | None = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def clear(self) -> None:
        self._root = None
        self._size = 0

    def insert(self,
        interval: Interval[T],
    ) -> None:
        """Insert an interval into the tree."""
        if not isinstance(interval, Interval):
            raise TypeError("expected Interval instance")
        self._root = self._insert_node(self._root, interval)
        self._size += 1

    def _insert_node(self,
        node: _IntervalNode[T] | None,
        interval: Interval[T],
    ) -> _IntervalNode[T]:
        if node is None:
            return _IntervalNode(interval)

        if interval.start < node.interval.start:
            node.left = self._insert_node(node.left, interval)
        else:
            node.right = self._insert_node(node.right, interval)

        node.max_end = max(
            node.interval.end,
            node.left.max_end if node.left else float("-inf"),
            node.right.max_end if node.right else float("-inf"),
        )
        return node

    def find_overlapping(self,
        query: Interval[Any] | tuple[float, float],
    ) -> list[Interval[T]]:
        """Find all intervals overlapping with query interval [start, end)."""
        if isinstance(query, tuple):
            q: Interval[Any] = Interval(query[0], query[1])
        else:
            q = query

        results: list[Interval[T]] = []

        def search(
            node: _IntervalNode[T] | None,
        ) -> None:
            if node is None:
                return
            if node.interval.overlaps(q):
                results.append(node.interval)

            if node.left and node.left.max_end > q.start:
                search(node.left)
            if node.right and node.interval.start < q.end:
                search(node.right)

        search(self._root)
        return sorted(results, key=lambda i: (i.start, i.end))

    def find_containing(self,
        point: float,
    ) -> list[Interval[T]]:
        """Find all intervals containing the given point."""
        return [iv for iv in self.find_overlapping(
            (point, point + 1e-9)) if iv.contains_point(point)]


__all__ = [
    "Interval",
    "IntervalTree",
]
