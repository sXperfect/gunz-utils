"""Strict binary reading/writing primitives."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    _accel = importlib.import_module("._accel", package=__package__)
    _accel_encode: Callable[[int], bytes] | None = getattr(
        _accel, "encode_uvarint", None
    )
    _accel_decode: Callable[[Any, int], tuple[int, int]] | None = getattr(
        _accel, "decode_uvarint", None
    )
except (ImportError, AttributeError):  # pragma: no cover
    _accel_encode = None
    _accel_decode = None



@dataclass
class ByteReader:
    data: memoryview
    offset: int = 0

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self.data = memoryview(data).cast("B")
        self.offset = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read(self, size: int) -> memoryview:
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("read size must be an integer")
        if size < 0 or size > self.remaining:
            raise EOFError("binary read exceeds available data")
        start = self.offset
        end = start + size
        chunk = self.data[start:end]
        self.offset = end
        return chunk

    def read_uvarint(self) -> int:
        """Read a canonical unsigned 64-bit varint transactionally."""
        if _accel_decode is not None:
            value, new_offset = _accel_decode(self.data, self.offset)
            self.offset = new_offset
            return value

        start = self.offset
        value = shift = 0
        try:
            for index in range(10):
                byte = int(self.read(1)[0])
                if index == 9 and byte > 1:
                    raise ValueError("varint exceeds 64 bits")
                value |= (byte & 0x7F) << shift
                if not byte & 0x80:
                    if index > 0 and byte == 0:
                        raise ValueError("non-canonical varint")
                    return value
                shift += 7
            raise ValueError("varint is too long")
        except BaseException:
            self.offset = start
            raise


def _py_encode_uvarint(value: int) -> bytes:
    if value < 0 or value > 2**64 - 1:
        raise ValueError("unsigned varint requires a 64-bit unsigned integer")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        output.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(output)


def encode_uvarint(value: int) -> bytes:
    """Encode an unsigned 64-bit integer into a canonical varint."""
    if _accel_encode is not None:
        return _accel_encode(value)
    return _py_encode_uvarint(value)


__all__ = ["ByteReader", "encode_uvarint"]

