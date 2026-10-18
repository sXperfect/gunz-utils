"""Strict binary reading/writing primitives."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

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
    _accel_encode_zigzag: Callable[[int], bytes] | None = getattr(
        _accel, "encode_zigzag", None
    )
    _accel_decode_zigzag: Callable[[Any, int], tuple[int, int]] | None = getattr(
        _accel, "decode_zigzag", None
    )
    _accel_decode_uvarints: (
        Callable[[Any, int, int], tuple[list[int], int]] | None
    ) = getattr(_accel, "fast_decode_uvarints", None)
    _accel_decode_zigzags: (
        Callable[[Any, int, int], tuple[list[int], int]] | None
    ) = getattr(_accel, "fast_decode_zigzags", None)
except (ImportError, AttributeError):  # pragma: no cover
    _accel_encode = None
    _accel_decode = None
    _accel_encode_zigzag = None
    _accel_decode_zigzag = None
    _accel_decode_uvarints = None
    _accel_decode_zigzags = None


@dataclass(slots=True)
class ByteReader:
    data: memoryview
    offset: int = 0

    def __init__(self,
        data: bytes | bytearray | memoryview,
    ) -> None:
        self.data = memoryview(data).cast("B")
        self.offset = 0

    @property
    def remaining(self) -> int:
        """remaining() property.

        Returns
        -------
        int
            The number of unread bytes remaining in the buffer.
        """
        return len(self.data) - self.offset

    def read(self,
        size: int,
    ) -> memoryview:
        """Read a specified number of bytes from the buffer.

        Parameters
        ----------
        size : int
            Number of bytes to read.

        Returns
        -------
        memoryview
            A memoryview slice of the read bytes.
        """
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
        """Read a canonical unsigned 64-bit varint transactionally.

        Returns
        -------
        int
            Decoded unsigned 64-bit integer.
        """
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

    def read_zigzag(self) -> int:
        """Read a canonical signed 64-bit zigzag varint transactionally.

        Returns
        -------
        int
            Decoded signed 64-bit integer.
        """
        if _accel_decode_zigzag is not None:
            value, new_offset = _accel_decode_zigzag(self.data, self.offset)
            self.offset = new_offset
            return value

        start = self.offset
        try:
            uval = self.read_uvarint()
            return (uval >> 1) ^ (-(uval & 1))
        except BaseException:
            self.offset = start
            raise

    def read_uvarints(self,
        count: int,
    ) -> list[int]:
        """Read a sequence of canonical unsigned varints transactionally.

        Parameters
        ----------
        count : int
            Number of unsigned varints to read. Must be non-negative.

        Returns
        -------
        list[int]
            List of decoded unsigned integers.
        """
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("count must be an integer (not bool)")
        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return []

        if _accel_decode_uvarints is not None:
            values, new_offset = _accel_decode_uvarints(self.data, self.offset, count)
            self.offset = new_offset
            return values

        start = self.offset
        try:
            return [self.read_uvarint() for _ in range(count)]
        except BaseException:
            self.offset = start
            raise

    def read_zigzags(self,
        count: int,
    ) -> list[int]:
        """Read a sequence of canonical signed zigzag varints transactionally.

        Parameters
        ----------
        count : int
            Number of zigzag varints to read. Must be non-negative.

        Returns
        -------
        list[int]
            List of decoded signed integers.
        """
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("count must be an integer (not bool)")
        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return []

        if _accel_decode_zigzags is not None:
            values, new_offset = _accel_decode_zigzags(self.data, self.offset, count)
            self.offset = new_offset
            return values

        start = self.offset
        try:
            return [self.read_zigzag() for _ in range(count)]
        except BaseException:
            self.offset = start
            raise


def _py_encode_uvarint(
    value: int,
) -> bytes:
    """Encode an unsigned 64-bit integer into a canonical varint in pure Python.

    Parameters
    ----------
    value : int
        Unsigned 64-bit integer.

    Returns
    -------
    bytes
        Encoded varint bytes.
    """
    if value < 0 or value > 2**64 - 1:
        raise ValueError("unsigned varint requires a 64-bit unsigned integer")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        output.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(output)


def _py_encode_zigzag(
    value: int,
) -> bytes:
    """Encode a signed 64-bit integer into a zigzag varint in pure Python.

    Parameters
    ----------
    value : int
        Signed 64-bit integer.

    Returns
    -------
    bytes
        Encoded zigzag varint bytes.
    """
    if value < -(2**63) or value > 2**63 - 1:
        raise ValueError("signed zigzag varint requires a 64-bit signed integer")
    uval = (value << 1) ^ (value >> 63)
    return _py_encode_uvarint(uval)


def encode_uvarint(
    value: int,
) -> bytes:
    """Encode an unsigned 64-bit integer into a canonical varint.

    Parameters
    ----------
    value : int
        Unsigned integer to encode.

    Returns
    -------
    bytes
        Encoded canonical varint bytes.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an integer (not bool)")
    if _accel_encode is not None:
        return _accel_encode(value)
    return _py_encode_uvarint(value)


def encode_zigzag(
    value: int,
) -> bytes:
    """Encode a signed 64-bit integer into a canonical zigzag varint.

    Parameters
    ----------
    value : int
        Signed integer to encode.

    Returns
    -------
    bytes
        Encoded canonical zigzag varint bytes.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an integer (not bool)")
    if _accel_encode_zigzag is not None:
        return _accel_encode_zigzag(value)
    return _py_encode_zigzag(value)


def decode_uvarint(
    data: bytes | bytearray | memoryview,
    offset: int = 0,
) -> tuple[int, int]:
    """Decode a canonical unsigned 64-bit varint from a buffer at offset.

    Parameters
    ----------
    data : bytes | bytearray | memoryview
        Input binary buffer.
    offset : int, optional
        Starting offset, by default 0.

    Returns
    -------
    tuple[int, int]
        Tuple of (decoded_value, new_offset).
    """
    reader = ByteReader(data)
    reader.offset = offset
    val = reader.read_uvarint()
    return val, reader.offset


def decode_zigzag(
    data: bytes | bytearray | memoryview,
    offset: int = 0,
) -> tuple[int, int]:
    """Decode a canonical signed 64-bit zigzag varint from a buffer at offset.

    Parameters
    ----------
    data : bytes | bytearray | memoryview
        Input binary buffer.
    offset : int, optional
        Starting offset, by default 0.

    Returns
    -------
    tuple[int, int]
        Tuple of (decoded_value, new_offset).
    """
    reader = ByteReader(data)
    reader.offset = offset
    val = reader.read_zigzag()
    return val, reader.offset


__all__ = [
    "ByteReader",
    "decode_uvarint",
    "decode_zigzag",
    "encode_uvarint",
    "encode_zigzag",
]
