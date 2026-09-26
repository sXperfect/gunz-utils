"""Streaming serialization and deterministic fingerprints."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
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
    """Hash canonical JSON without exposing representation-order differences."""
    digest = hashlib.new(algorithm)
    digest.update(canonical_json(value).encode("utf-8"))
    return digest.hexdigest()


def hash_stream(handle: BinaryIO, *, algorithm: str = "sha256", chunk_size: int = 1 << 20) -> str:
    """Hash a binary stream with bounded memory."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.new(algorithm)
    while chunk := handle.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest()


__all__ = ["fingerprint", "hash_stream", "iter_jsonl", "write_jsonl"]
