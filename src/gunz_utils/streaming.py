"""Streaming serialization, bounded writers, and deterministic fingerprints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO, TextIO

from .serialization import canonical_json


def iter_jsonl(handle: TextIO) -> Iterator[Any]:
    """Decode non-empty JSON Lines records lazily."""
    for line in handle:
        if line.strip():
            yield json.loads(line)


def write_jsonl(handle: TextIO, records: Iterable[Any]) -> int:
    """Write compact JSON Lines records and return the record count."""
    count = 0
    for record in records:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        count += 1
    return count


def fingerprint(value: Any, algorithm: str = "sha256") -> str:
    """Hash canonical JSON without representation-order differences."""
    digest = hashlib.new(algorithm)
    digest.update(canonical_json(value).encode("utf-8"))
    return digest.hexdigest()


def hash_stream(
    handle: BinaryIO,
    *,
    algorithm: str = "sha256",
    chunk_size: int = 1 << 20,
) -> str:
    """Hash a binary stream with bounded memory."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.new(algorithm)
    while chunk := handle.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest()


class BoundedWriter:
    """Binary writer that rejects writes exceeding a cumulative byte limit."""

    def __init__(self, handle: BinaryIO, *, max_bytes: int) -> None:
        if max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        self.handle = handle
        self.max_bytes = max_bytes
        self.bytes_written = 0

    def write(self, data: bytes) -> int:
        """Write all bytes without exceeding the configured limit."""
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
    """Binary writer that hashes written bytes and can enforce a byte limit."""

    def __init__(
        self,
        handle: BinaryIO,
        *,
        algorithm: str = "sha256",
        max_bytes: int | None = None,
    ) -> None:
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        self.handle = handle
        self.algorithm = algorithm
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self._digest = hashlib.new(algorithm)

    def write(self, data: bytes) -> int:
        """Write and hash all bytes, handling partial underlying writes."""
        if (
            self.max_bytes is not None
            and self.bytes_written + len(data) > self.max_bytes
        ):
            raise ValueError("write exceeds byte limit")
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
        """Return the digest for bytes successfully written so far."""
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
    """Copy a binary stream while hashing and optionally bounding output size."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    writer = DigestWriter(
        destination,
        algorithm=algorithm,
        max_bytes=max_bytes,
    )
    while chunk := source.read(chunk_size):
        writer.write(chunk)
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
