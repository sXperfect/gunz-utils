"""Reusable bounded data structures and stream algorithms."""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Iterable, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class RingBuffer(Generic[T]):
    """Fixed-capacity FIFO retaining the newest values."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._data: deque[T] = deque(maxlen=capacity)

    def append(self, value: T) -> None:
        self._data.append(value)

    def __iter__(self) -> Iterator[T]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


def top_k(items: Iterable[T], k: int) -> list[T]:
    """Return the largest k values without sorting the complete input."""
    if k < 0:
        raise ValueError("k must be non-negative")
    return heapq.nlargest(k, items)


def stable_unique(items: Iterable[T]) -> Iterator[T]:
    """Yield hashable values once while preserving first-seen order."""
    seen: set[T] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            yield item


__all__ = ["RingBuffer", "stable_unique", "top_k"]
