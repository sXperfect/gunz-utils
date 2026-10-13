"""Streaming serialization, bounded writers, and deterministic fingerprints."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO, TextIO

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .serialization import _MAX_JSON_DEPTH, _excessive_nesting_position, canonical_json


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


def _reject_nonfinite(value: Any) -> None:
    """Raise ``ValueError`` if ``value`` decodes to a non-finite float.

    ``parse_constant`` only intercepts the non-standard ``NaN``/``Infinity``
    literals; an ordinary JSON numeric literal that overflows the float range
    (e.g. ``1e400``) decodes to ``float('inf')``/``-inf`` without error. This
    walker rejects any such record so the reader stays symmetric with the
    ``allow_nan=False`` writer. It is iterative so deep records do not
    overflow the interpreter stack.
    """
    stack: list[Any] = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, float):
            if not math.isfinite(node):
                raise ValueError(f"non-finite JSON number: {node}")
        elif isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def iter_jsonl(
    handle: TextIO,
) -> Iterator[Any]:
    """Decode non-empty JSON Lines records lazily.

    Parameters
    ----------
    handle : TextIO
        handle parameter.

    Returns
    -------
    Iterator[Any]
        The result of the operation.

    Raises
    ------
    ValueError
        If a record uses a non-standard constant or decodes to a non-finite
        float (e.g. an overflowing numeric literal).
    """
    for line in handle:
        if line.strip():
            #? Apply the package's shared JSON nesting-depth bound before
            #? parsing (matching serialization.json_loads) so a record nested
            #? deeper than the encode-side bound is rejected with ValueError
            #? instead of silently accepted or surfacing a raw RecursionError.
            position = _excessive_nesting_position(line, _MAX_JSON_DEPTH)
            if position >= 0:
                raise json.JSONDecodeError(
                    f"JSON record is nested deeper than {_MAX_JSON_DEPTH} levels",
                    line,
                    position,
                )
            record = json.loads(line, parse_constant=_reject_json_constant)
            _reject_nonfinite(record)
            yield record


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
    count = 0
    buffer: list[str] = []
    for record in records:
        buffer.append(
            json.dumps(
                record,
                separators=(",", ":"),
                allow_nan=False,
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

    def write(self,
        data: bytes,
    ) -> int:
        """Write all bytes without exceeding the configured limit.

        Parameters
        ----------
        data : bytes
            data parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        if self.bytes_written + len(data) > self.max_bytes:
            raise ValueError("write exceeds byte limit")
        view = memoryview(data)
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
    """Binary writer that hashes written bytes and truncates at a byte limit.

    Unlike :class:`BoundedWriter`, which rejects writes that exceed its
    limit, this writer silently truncates input at ``max_bytes`` so a bounded
    copy-and-hash can complete on an oversized source.
    """

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

    def write(self,
        data: bytes,
    ) -> int:
        """Write and hash bytes, truncating at the configured limit, and
        handle partial underlying writes.

        Parameters
        ----------
        data : bytes
            data parameter.

        Returns
        -------
        int
            The result of the operation.
        """
        if self.max_bytes is not None:
            remaining = self.max_bytes - self.bytes_written
            if remaining <= 0:
                return 0
            if len(data) > remaining:
                data = data[:remaining]
        view = memoryview(data)
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
        #? Stop pulling from the source once the byte bound is reached so an
        #? oversized source is not read to EOF.
        if max_bytes is not None and writer.bytes_written >= max_bytes:
            break
    return StreamCopyResult(writer.bytes_written, writer.hexdigest)


__all__ = [
    "BoundedWriter",
    "DigestWriter",
    "StreamCopyResult",
    "copy_and_hash",
    "fingerprint",
    "hash_stream",
    "iter_jsonl",
    "write_jsonl",
]
