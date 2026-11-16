"""Zero-copy buffer utilities and backend dispatch."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def as_readonly_view(
    data: bytes | bytearray | memoryview,
) -> memoryview:
    """Return a byte-oriented readonly view without copying when possible.

    Parameters
    ----------
    data : bytes | bytearray | memoryview
        Binary buffer object.

    Returns
    -------
    memoryview
        Readonly byte-oriented memoryview.

    Raises
    ------
    TypeError
        If data does not support the buffer protocol.
    """
    try:
        view = memoryview(data)
    except TypeError as exc:
        raise TypeError(
            f"expected a bytes-like object, got {type(data).__name__}") from exc
    try:
        byte_view = view.cast("B")
    except (BufferError, TypeError, ValueError):
        byte_view = memoryview(bytes(view))
    return byte_view.toreadonly()


def dispatch(
    reference: Callable[..., T],
    accelerated: Callable[..., T] | None = None,
) -> Callable[..., T]:
    """Select an optional accelerated implementation without making it required.

    Parameters
    ----------
    reference : Callable[..., T]
        Reference Python implementation.
    accelerated : Callable[..., T] | None
        Accelerated implementation, or None.

    Returns
    -------
    Callable[..., T]
        Accelerated callable if provided, else reference.

    Raises
    ------
    TypeError
        If reference or accelerated is not callable.
    """
    if not callable(reference):
        raise TypeError("reference must be callable")
    if accelerated is not None and not callable(accelerated):
        raise TypeError("accelerated must be callable or None")
    return reference if accelerated is None else accelerated


class RingBuffer:
    """Fixed-capacity circular byte buffer for binary streaming."""

    def __init__(self,
        capacity: int,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an integer")
        if capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._buf = bytearray(capacity)
        self._head = 0
        self._tail = 0
        self._size = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def is_full(self) -> bool:
        return self._size == self._capacity

    @property
    def is_empty(self) -> bool:
        return self._size == 0

    @property
    def available_read(self) -> int:
        return self._size

    @property
    def available_write(self) -> int:
        return self._capacity - self._size

    def __len__(self) -> int:
        return self._size

    def __bytes__(self) -> bytes:
        return self.peek()

    def write(self,
        data: bytes | bytearray | memoryview,
    ) -> int:
        view = as_readonly_view(data)
        to_write = min(len(view), self.available_write)
        if to_write == 0:
            return 0
        first_chunk = min(to_write, self._capacity - self._tail)
        self._buf[self._tail : self._tail + first_chunk] = view[:first_chunk]
        second_chunk = to_write - first_chunk
        if second_chunk > 0:
            self._buf[:second_chunk] = view[first_chunk:to_write]
        self._tail = (self._tail + to_write) % self._capacity
        self._size += to_write
        return to_write

    def read(self,
        n: int | None = None,
    ) -> bytes:
        if n is None:
            n = self._size
        elif isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("n must be a non-negative integer or None")
        to_read = min(n, self._size)
        if to_read == 0:
            return b""
        out = self.peek(to_read)
        self._head = (self._head + to_read) % self._capacity
        self._size -= to_read
        return out

    def peek(self,
        n: int | None = None,
    ) -> bytes:
        if n is None:
            n = self._size
        elif isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("n must be a non-negative integer or None")
        to_peek = min(n, self._size)
        if to_peek == 0:
            return b""
        first_chunk = min(to_peek, self._capacity - self._head)
        part1 = self._buf[self._head : self._head + first_chunk]
        second_chunk = to_peek - first_chunk
        if second_chunk > 0:
            part2 = self._buf[:second_chunk]
            return bytes(part1 + part2)
        return bytes(part1)

    def discard(self,
        n: int,
    ) -> int:
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("n must be a non-negative integer")
        to_discard = min(n, self._size)
        self._head = (self._head + to_discard) % self._capacity
        self._size -= to_discard
        return to_discard

    def clear(self) -> None:
        self._head = 0
        self._tail = 0
        self._size = 0


class ChunkedBuffer:
    """Zero-copy accumulator for binary memoryview chunks."""

    def __init__(self) -> None:
        self._chunks: list[memoryview] = []
        self._total_bytes = 0

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    def __len__(self) -> int:
        return self._total_bytes

    def append(self,
        data: bytes | bytearray | memoryview,
    ) -> None:
        view = as_readonly_view(data)
        if len(view) > 0:
            self._chunks.append(view)
            self._total_bytes += len(view)

    def to_bytes(self) -> bytes:
        if not self._chunks:
            return b""
        if len(self._chunks) == 1:
            return bytes(self._chunks[0])
        return b"".join(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()
        self._total_bytes = 0


__all__ = [
    "ChunkedBuffer",
    "RingBuffer",
    "as_readonly_view",
    "dispatch",
]
