"""Streaming serialization, bounded writers, and deterministic fingerprints."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import math
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO, TextIO, TypeVar

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .serialization import canonical_json, to_jsonable

T = TypeVar("T")


def _reject_json_constant(
    value: str,
) -> object:
    """_reject_json_constant() function.

    Parameters
    ----------
    value : str
        value parameter.

    Returns
    -------
    object
        The result of the operation.
    """
    raise ValueError(f"non-standard JSON constant: {value}")


def _check_float(
    value: str,
) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite float in JSON: {value}")
    return number


def _iter_jsonl_gen(
    handle: TextIO,
    max_line_length: int | None,
) -> Iterator[Any]:
    if max_line_length is not None:
        while True:
            line = handle.readline(max_line_length + 1)
            if not line:
                break
            if len(line) > max_line_length or (
    not line.endswith("\n") and bool(
        handle.readline(1))):
                raise ValueError(
                    f"JSON Lines record exceeds maximum line length ({max_line_length})"
                )
            if line.strip():
                yield json.loads(
                    line,
                    parse_constant=_reject_json_constant,
                    parse_float=_check_float,
                )
    else:
        for line in handle:
            if line.strip():
                yield json.loads(
                    line,
                    parse_constant=_reject_json_constant,
                    parse_float=_check_float,
                )


def iter_jsonl(
    handle: TextIO,
    *,
    max_line_length: int | None = None,
) -> Iterator[Any]:
    """Decode non-empty JSON Lines records lazily.

    Parameters
    ----------
    handle : TextIO
        Text stream open for reading JSON Lines records.
    max_line_length : int | None, optional
        Maximum allowed character length for any single line in the stream.
        If a line exceeds this length, ValueError is raised. Defaults to None
        (unlimited).

    Yields
    ------
    Any
        The decoded JSON object for each non-empty line.

    Raises
    ------
    ValueError
        If ``max_line_length`` is not a positive integer or None, if any line
        exceeds ``max_line_length``, or if a line contains non-standard JSON
        constants.
    TypeError
        If ``handle`` is not a readable stream.
    """
    if handle is None or not hasattr(handle, "readline"):
        raise TypeError("handle must be a readable text stream")
    if max_line_length is not None and (
        isinstance(max_line_length, bool)
        or not isinstance(max_line_length, int)
        or max_line_length <= 0
    ):
        raise ValueError("max_line_length must be a positive integer or None")

    return _iter_jsonl_gen(handle, max_line_length)


def write_jsonl(
    handle: TextIO,
    records: Iterable[Any],
) -> int:
    """Write compact JSON Lines records and return the record count.

    Parameters
    ----------
    handle : TextIO
        handle parameter.
    records : Iterable[Any]
        records parameter.

    Returns
    -------
    int
        The result of the operation.
    """
    if handle is None or not hasattr(handle, "write"):
        raise TypeError("handle must be a writable text stream")
    if isinstance(records, (str, bytes, bytearray, memoryview)):
        raise TypeError("records must be an iterable of objects, not a string or bytes")
    count = 0
    buffer: list[str] = []
    for record in records:
        buffer.append(
            json.dumps(
                to_jsonable(record),
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        count += 1
        if len(buffer) >= 256:
            handle.write("".join(buffer))
            buffer.clear()
    if buffer:
        handle.write("".join(buffer))
    return count



def fingerprint(
    value: Any,
    algorithm: str = "sha256",
) -> str:
    """Hash canonical JSON without representation-order differences.

    Parameters
    ----------
    value : Any
        value parameter.
    algorithm : str
        algorithm parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    digest = hashlib.new(algorithm)
    digest.update(canonical_json(value).encode("utf-8"))
    return digest.hexdigest()


def hash_stream(
    handle: BinaryIO,
    *,
    algorithm: str = "sha256",
    chunk_size: int = 1 << 20,
) -> str:
    """Hash a binary stream with bounded memory.

    Parameters
    ----------
    handle : BinaryIO
        handle parameter.
    algorithm : str
        algorithm parameter.
    chunk_size : int
        chunk_size parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size < 1
    ):
        raise ValueError("chunk_size must be a positive integer")
    digest = hashlib.new(algorithm)
    while chunk := handle.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest()


class BoundedWriter:
    """Binary writer that rejects writes exceeding a cumulative byte limit."""

    def __init__(self,
        handle: BinaryIO,
        *,
        max_bytes: int,
    ) -> None:
        if (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or max_bytes < 0
        ):
            raise ValueError("max_bytes must be a non-negative integer")
        self.handle = handle
        self.max_bytes = max_bytes
        self.bytes_written = 0

    @property
    def remaining_bytes(self) -> int:
        """Return the number of additional bytes that can be written."""
        return max(0, self.max_bytes - self.bytes_written)

    def flush(self) -> None:
        """Flush the underlying stream if supported."""
        if hasattr(self.handle, "flush") and callable(self.handle.flush):
            self.handle.flush()

    def __enter__(self) -> BoundedWriter:
        return self

    def __exit__(self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is None:
            self.flush()

    def write(self,
        data: bytes | bytearray | memoryview,
    ) -> int:
        """Write all bytes without exceeding the configured limit.

        Parameters
        ----------
        data : bytes | bytearray | memoryview
            data parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        view = memoryview(data).cast("B")
        if self.bytes_written + len(view) > self.max_bytes:
            raise ValueError("write exceeds byte limit")
        offset = 0
        while offset < len(view):
            written = self.handle.write(view[offset:])
            if written is None or written <= 0:
                raise OSError("binary stream made no forward progress")
            if written > len(view) - offset:
                raise OSError("binary stream reported an invalid write count")
            offset += written
            self.bytes_written += written
        return offset


class DigestWriter:
    """Binary writer that hashes written bytes and can enforce a byte limit."""

    def __init__(self,
        handle: BinaryIO,
        *,
        algorithm: str = "sha256",
        max_bytes: int | None = None,
    ) -> None:
        if max_bytes is not None and (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or max_bytes < 0
        ):
            raise ValueError("max_bytes must be a non-negative integer or None")
        self.handle = handle
        self.algorithm = algorithm
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self._digest = hashlib.new(algorithm)

    def flush(self) -> None:
        """Flush the underlying stream if supported."""
        if hasattr(self.handle, "flush") and callable(self.handle.flush):
            self.handle.flush()

    def __enter__(self) -> DigestWriter:
        return self

    def __exit__(self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is None:
            self.flush()

    def write(self,
        data: bytes | bytearray | memoryview,
    ) -> int:
        """Write and hash all bytes, handling partial underlying writes.

        Parameters
        ----------
        data : bytes | bytearray | memoryview
            data parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        view = memoryview(data).cast("B")
        if (
            self.max_bytes is not None
            and self.bytes_written + len(view) > self.max_bytes
        ):
            raise ValueError("write exceeds byte limit")
        offset = 0
        while offset < len(view):
            written = self.handle.write(view[offset:])
            if written is None or written <= 0:
                raise OSError("binary stream made no forward progress")
            if written > len(view) - offset:
                raise OSError("binary stream reported an invalid write count")
            self._digest.update(view[offset : offset + written])
            offset += written
            self.bytes_written += written
        return offset

    @property
    def hexdigest(self) -> str:
        """Return the digest for bytes successfully written so far.

        Returns
        -------
        str
            The result of the operation.
        """
        return self._digest.hexdigest()


@dataclass(frozen=True, slots=True)
class StreamCopyResult:
    """Summary of a bounded copy-and-hash operation."""

    bytes_written: int
    hexdigest: str


def copy_and_hash(
    source: BinaryIO,
    destination: BinaryIO,
    *,
    algorithm: str = "sha256",
    chunk_size: int = 1 << 20,
    max_bytes: int | None = None,
) -> StreamCopyResult:
    """Copy a binary stream while hashing and optionally bounding output size.

    Parameters
    ----------
    source : BinaryIO
        source parameter.
    destination : BinaryIO
        destination parameter.
    algorithm : str
        algorithm parameter.
    chunk_size : int
        chunk_size parameter.
    max_bytes : int | None
        max_bytes parameter.

    Returns
    -------
    StreamCopyResult
        The result of the operation.
    """
    if not callable(getattr(source, "read", None)):
        raise TypeError("source must have a callable read method")
    if not callable(getattr(destination, "write", None)):
        raise TypeError("destination must have a callable write method")
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size < 1
    ):
        raise ValueError("chunk_size must be a positive integer")
    writer = DigestWriter(
        destination,
        algorithm=algorithm,
        max_bytes=max_bytes,
    )
    while chunk := source.read(chunk_size):
        writer.write(chunk)
    return StreamCopyResult(writer.bytes_written, writer.hexdigest)


def stream_windowed(
    iterable: Iterable[T],
    size: int,
    step: int = 1,
) -> Iterator[tuple[T, ...]]:
    """Yield sliding windows of fixed size over an iterable.

    Parameters
    ----------
    iterable : Iterable[T]
        Sequence or generator to slice into sliding windows.
    size : int
        Window size (must be >= 1).
    step : int, optional
        Step between consecutive window starts (must be >= 1, default 1).

    Yields
    ------
    tuple[T, ...]
        Tuples of length ``size``.
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("size must be an integer >= 1")
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise ValueError("step must be an integer >= 1")

    it = iter(iterable)
    buf: deque[T] = deque()
    for item in it:
        buf.append(item)
        if len(buf) == size:
            yield tuple(buf)
            for _ in range(min(step, size)):
                buf.popleft()
            for _ in range(step - size):
                try:
                    next(it)
                except StopIteration:
                    return


def stream_batch(
    iterable: Iterable[T],
    max_size: int,
) -> Iterator[list[T]]:
    """Chunk an iterable into fixed-capacity lists.

    Parameters
    ----------
    iterable : Iterable[T]
        Stream of items to batch.
    max_size : int
        Maximum number of items per batch (must be >= 1).

    Yields
    ------
    list[T]
        Batches with size between 1 and ``max_size``.
    """
    if isinstance(max_size, bool) or not isinstance(max_size, int) or max_size < 1:
        raise ValueError("max_size must be an integer >= 1")

    batch: list[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= max_size:
            yield batch
            batch = []
    if batch:
        yield batch


def stream_filter_none(
    iterable: Iterable[T | None],
) -> Iterator[T]:
    """Filter out None elements from an iterable.

    Parameters
    ----------
    iterable : Iterable[T | None]
        Input stream containing possible None elements.

    Yields
    ------
    T
        Non-None items.
    """
    for item in iterable:
        if item is not None:
            yield item


def stream_interleave(
    *iterables: Iterable[T],
) -> Iterator[T]:
    """Round-robin interleave elements from multiple iterables until all are exhausted.

    Parameters
    ----------
    *iterables : Iterable[T]
        Iterables to interleave.

    Yields
    ------
    T
        Interleaved elements in round-robin order.
    """
    active = deque(iter(it) for it in iterables)
    while active:
        it = active.popleft()
        try:
            val = next(it)
            yield val
            active.append(it)
        except StopIteration:
            pass


def stream_take_while(
    iterable: Iterable[T],
    predicate: Callable[[T], bool],
) -> Iterator[T]:
    """Yield items from iterable as long as predicate is true."""
    for item in iterable:
        if predicate(item):
            yield item
        else:
            break


def stream_drop_while(
    iterable: Iterable[T],
    predicate: Callable[[T], bool],
) -> Iterator[T]:
    """Drop items from iterable as long as predicate is true, then yield remaining."""
    it = iter(iterable)
    for item in it:
        if not predicate(item):
            yield item
            break
    for item in it:
        yield item


def stream_peek(
    iterable: Iterable[T],
    n: int = 1,
) -> tuple[list[T], Iterator[T]]:
    """Look ahead at the next n items without consuming them from the returned iterator.

    Parameters
    ----------
    iterable : Iterable[T]
        Input stream.
    n : int
        Number of items to preview (must be >= 0).

    Returns
    -------
    tuple[list[T], Iterator[T]]
        A list of peeked items, and a reconstructed iterator with all original items.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be an integer >= 0")
    it = iter(iterable)
    peeked: list[T] = []
    for _ in range(n):
        try:
            peeked.append(next(it))
        except StopIteration:
            break
    return peeked, itertools.chain(peeked, it)


def stream_tee(
    iterable: Iterable[T],
    n: int = 2,
) -> tuple[Iterator[T], ...]:
    """Split an iterable into n independent iterators.

    Parameters
    ----------
    iterable : Iterable[T]
        Input iterable.
    n : int
        Number of branches (must be >= 0).
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be an integer >= 0")
    return itertools.tee(iterable, n)


def stream_drain(
    iterable: Iterable[Any],
) -> int:
    """Consume an iterable completely and return the total number of items drained."""
    count = 0
    for _ in iterable:
        count += 1
    return count


class AsyncStreamBuffer:
    """Asynchronous bounded in-memory byte buffer with EOF signaling."""

    def __init__(self,
        max_bytes: int = 0,
    ) -> None:
        if isinstance(
    max_bytes,
    bool) or not isinstance(
        max_bytes,
         int) or max_bytes < 0:
            raise ValueError("max_bytes must be a non-negative integer")
        self.max_bytes = max_bytes
        self._buffer = bytearray()
        self._eof = False
        self._event = asyncio.Event()

    def is_eof(self) -> bool:
        """Return True if EOF has been signaled and buffer is empty."""
        return self._eof and len(self._buffer) == 0

    def write_eof(self) -> None:
        """Signal EOF to waiting readers."""
        self._eof = True
        self._event.set()

    async def write(self,
        data: bytes | bytearray | memoryview,
    ) -> int:
        """Write bytes to the buffer."""
        if self._eof:
            raise RuntimeError("cannot write to closed buffer")
        view = memoryview(data).cast("B")
        if self.max_bytes > 0 and len(self._buffer) + len(view) > self.max_bytes:
            raise ValueError("buffer capacity exceeded")
        self._buffer.extend(view)
        self._event.set()
        return len(view)

    async def read(self,
        n: int = -1,
    ) -> bytes:
        """Read up to n bytes from buffer, waiting if empty until data or EOF."""
        if n == 0:
            return b""
        while len(self._buffer) == 0:
            if self._eof:
                return b""
            self._event.clear()
            await self._event.wait()

        if n < 0 or n >= len(self._buffer):
            out = bytes(self._buffer)
            self._buffer.clear()
            return out

        out = bytes(self._buffer[:n])
        del self._buffer[:n]
        return out


class AsyncDelimitedReader:
    """Asynchronous reader that streams chunks until a delimiter is encountered."""

    def __init__(self,
        stream: Any,
    ) -> None:
        if not hasattr(stream, "read"):
            raise TypeError("stream must provide an async read(n) method")
        self.stream = stream
        self._buffer = bytearray()

    async def read_until(self,
        delimiter: bytes = b"\n",
        max_bytes: int | None = None,
    ) -> bytes:
        """Read until delimiter is reached or EOF.

        Parameters
        ----------
        delimiter : bytes
            Byte sequence marking the end of a record.
        max_bytes : int | None
            Maximum allowed bytes before raising a ValueError.

        Returns
        -------
        bytes
            Bytes up to and including delimiter, or all remaining bytes at EOF.
        """
        if not delimiter:
            raise ValueError("delimiter must not be empty")

        while True:
            idx = self._buffer.find(delimiter)
            if idx != -1:
                end = idx + len(delimiter)
                res = bytes(self._buffer[:end])
                del self._buffer[:end]
                return res

            if max_bytes is not None and len(self._buffer) >= max_bytes:
                raise ValueError(
                    f"delimiter not found within max_bytes limit ({max_bytes})")

            chunk = await self.stream.read(4096)
            if not chunk:
                #? EOF reached
                res = bytes(self._buffer)
                self._buffer.clear()
                return res
            self._buffer.extend(chunk)


__all__ = [
    "AsyncDelimitedReader",
    "AsyncStreamBuffer",
    "BoundedWriter",
    "DigestWriter",
    "StreamCopyResult",
    "copy_and_hash",
    "fingerprint",
    "hash_stream",
    "iter_jsonl",
    "stream_batch",
    "stream_drain",
    "stream_drop_while",
    "stream_filter_none",
    "stream_interleave",
    "stream_peek",
    "stream_take_while",
    "stream_tee",
    "stream_windowed",
    "write_jsonl",
]
