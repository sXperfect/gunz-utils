"""Strict binary reading/writing primitives."""

from __future__ import annotations

from dataclasses import dataclass


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
        if size < 0 or size > self.remaining:
            raise EOFError("binary read exceeds available data")
        start = self.offset
        self.offset += size
        return self.data[start:self.offset]

    def read_uvarint(self) -> int:
        """Read a canonical unsigned 64-bit varint transactionally."""
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


def encode_uvarint(value: int) -> bytes:
    if value < 0 or value > 2**64 - 1:
        raise ValueError("unsigned varint requires a 64-bit unsigned integer")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        output.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(output)


__all__ = ["ByteReader", "encode_uvarint"]
