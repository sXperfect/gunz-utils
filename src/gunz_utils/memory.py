"""Memory-efficient chunk pools, sliding byte buffers, and non-contiguous byte streams.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class MemoryChunkPool:
    """Pre-allocated pool of reusable bytearrays to minimize GC overhead."""

    def __init__(self,
        chunk_size: int = 65536,
        max_chunks: int = 16,
    ) -> None:
        if chunk_size < 1 or max_chunks < 1:
            raise ValueError("chunk_size and max_chunks must be positive integers")
        self.chunk_size = chunk_size
        self.max_chunks = max_chunks
        self._pool: list[bytearray] = []
        self._lock = threading.Lock()

    def acquire(self) -> bytearray:
        """Acquire a bytearray of length chunk_size from pool."""
        with self._lock:
            if self._pool:
                return self._pool.pop()
        return bytearray(self.chunk_size)

    def release(self,
        chunk: bytearray,
    ) -> None:
        """Return a chunk to the pool."""
        if len(chunk) != self.chunk_size:
            return  #? wrong size, discard
        with self._lock:
            if len(self._pool) < self.max_chunks:
                self._pool.append(chunk)

    @contextmanager
    def scoped(self) -> Iterator[bytearray]:
        """Context manager leasing a chunk for the duration of the block."""
        chunk = self.acquire()
        try:
            yield chunk
        finally:
            self.release(chunk)


class SlidingByteBuffer:
    """Sliding-window byte buffer for stream parsing and pattern lookahead."""

    def __init__(self,
        capacity: int = 65536,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    def write(self,
        data: bytes | bytearray | memoryview,
    ) -> int:
        """Append bytes to buffer. Raises BufferError if capacity exceeded."""
        view = memoryview(data).cast("B")
        with self._lock:
            if len(self._buffer) + len(view) > self.capacity:
                raise BufferError(f"buffer capacity ({self.capacity}) exceeded")
            self._buffer.extend(view)
        return len(view)

    def read(self,
        n: int = -1,
    ) -> bytes:
        """Consume and return up to n bytes from front of buffer."""
        with self._lock:
            if not self._buffer:
                return b""
            if n < 0 or n >= len(self._buffer):
                res = bytes(self._buffer)
                self._buffer.clear()
                return res
            res = bytes(self._buffer[:n])
            del self._buffer[:n]
            return res

    def peek(self,
        n: int = -1,
    ) -> bytes:
        """Preview up to n bytes from front of buffer without consuming."""
        with self._lock:
            if not self._buffer:
                return b""
            if n < 0 or n >= len(self._buffer):
                return bytes(self._buffer)
            return bytes(self._buffer[:n])

    def find(self,
        sub: bytes,
    ) -> int:
        """Return index of byte substring in buffer, or -1 if not found."""
        with self._lock:
            return self._buffer.find(sub)


class ChunkedMemoryStream:
    """Non-contiguous memory stream built on chunks avoiding massive continuous
    reallocations.
    """

    def __init__(self,
        chunk_size: int = 65536,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")
        self.chunk_size = chunk_size
        self._chunks: list[bytearray] = []
        self._write_pos: int = 0
        self._read_pos: int = 0

    def write(self,
        data: bytes | bytearray | memoryview,
    ) -> int:
        """Append data to the stream."""
        view = memoryview(data).cast("B")
        offset = 0
        total = len(view)

        while offset < total:
            if not self._chunks or len(self._chunks[-1]) == self.chunk_size:
                self._chunks.append(bytearray())
            curr_chunk = self._chunks[-1]
            space = self.chunk_size - len(curr_chunk)
            take = min(space, total - offset)
            curr_chunk.extend(view[offset : offset + take])
            offset += take
            self._write_pos += take

        return total

    def read(self,
        n: int = -1,
    ) -> bytes:
        """Read up to n bytes from the stream."""
        if n == 0 or self._read_pos >= self._write_pos:
            return b""

        to_read = self._write_pos - \
            self._read_pos if n < 0 else min(n, self._write_pos - self._read_pos)
        out = bytearray(to_read)
        out_offset = 0

        while out_offset < to_read:
            chunk_idx = self._read_pos // self.chunk_size
            in_chunk_offset = self._read_pos % self.chunk_size
            chunk = self._chunks[chunk_idx]
            avail = len(chunk) - in_chunk_offset
            take = min(avail, to_read - out_offset)
            out[out_offset : out_offset + \
                take] = chunk[in_chunk_offset : in_chunk_offset + take]
            self._read_pos += take
            out_offset += take

        return bytes(out)

    def getvalue(self) -> bytes:
        """Return all written bytes as a single bytes object."""
        return bytes(b"".join(self._chunks))

    def tell(self) -> int:
        """Return current read position."""
        return self._read_pos

    def seek(self,
        pos: int,
    ) -> int:
        """Set current read position."""
        if not (0 <= pos <= self._write_pos):
            raise ValueError(f"seek position {pos} out of range (0..{self._write_pos})")
        self._read_pos = pos
        return self._read_pos


__all__ = [
    "ChunkedMemoryStream",
    "MemoryChunkPool",
    "SlidingByteBuffer",
]
