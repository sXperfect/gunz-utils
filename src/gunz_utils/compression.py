"""Magic-byte format detection, bounded decompression guards, and stream compression."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import bz2
import gzip
import io
import lzma
import math
import zlib
from enum import Enum
from typing import BinaryIO


class CompressionFormat(str, Enum):
    """Supported archive and compression formats."""

    GZIP = "GZIP"
    BZIP2 = "BZIP2"
    XZ = "XZ"
    ZLIB = "ZLIB"
    RAW = "RAW"


class DecompressionLimitExceeded(ValueError):
    """Raised when decompression exceeds the configured maximum byte bound."""


def detect_compression_format(
    header_bytes: bytes,
) -> CompressionFormat:
    """Detect compression format from leading magic bytes."""
    if len(header_bytes) >= 2 and header_bytes[:2] == b"\x1f\x8b":
        return CompressionFormat.GZIP
    if len(header_bytes) >= 3 and header_bytes[:3] == b"BZh":
        return CompressionFormat.BZIP2
    if len(header_bytes) >= 6 and header_bytes[:6] == b"\xfd7zXZ\x00":
        return CompressionFormat.XZ
    if len(header_bytes) >= 2 and header_bytes[0] == 0x78 and header_bytes[1] in (
        0x01, 0x5E, 0x9C, 0xDA):
        return CompressionFormat.ZLIB
    return CompressionFormat.RAW


def compress_gzip(
    data: bytes,
    level: int = 6,
) -> bytes:
    """Compress bytes using gzip."""
    return gzip.compress(data, compresslevel=level)


def decompress_gzip(
    data: bytes,
    max_bytes: int | None = None,
) -> bytes:
    """Decompress gzip bytes with optional size bound."""
    return decompress_bounded(
    data, max_output_bytes=max_bytes or (
        100 * len(data) + 1024 * 1024))


def compress_zlib(
    data: bytes,
    level: int = 6,
) -> bytes:
    """Compress bytes using zlib."""
    return zlib.compress(data, level=level)


def decompress_zlib(
    data: bytes,
    max_bytes: int | None = None,
) -> bytes:
    """Decompress zlib bytes with optional size bound."""
    return decompress_bounded(
    data, max_output_bytes=max_bytes or (
        100 * len(data) + 1024 * 1024))


def decompress_bounded(
    data: bytes,
    max_output_bytes: int = 10_485_760,
) -> bytes:
    """Decompress data with zip-bomb protection and format autodetection."""
    fmt = detect_compression_format(data)
    if fmt == CompressionFormat.RAW:
        if len(data) > max_output_bytes:
            raise DecompressionLimitExceeded(
                "uncompressed payload exceeds maximum bound")
        return data

    out = bytearray()
    chunk_size = 65536

    if fmt == CompressionFormat.GZIP:
        decompressor = gzip.GzipFile(fileobj=io.BytesIO(data))
        while chunk := decompressor.read(chunk_size):
            out.extend(chunk)
            if len(out) > max_output_bytes:
                raise DecompressionLimitExceeded(
                    f"decompression output exceeded limit ({max_output_bytes} bytes)"
                )
        return bytes(out)

    if fmt == CompressionFormat.ZLIB:
        decomp = zlib.decompressobj()
        chunk = decomp.decompress(data, max_output_bytes + 1)
        if len(chunk) > max_output_bytes or decomp.unconsumed_tail:
            raise DecompressionLimitExceeded(
                f"decompression output exceeded limit ({max_output_bytes} bytes)"
            )
        return chunk

    if fmt == CompressionFormat.BZIP2:
        decomp_bz = bz2.BZ2Decompressor()
        chunk = decomp_bz.decompress(data, max_output_bytes + 1)
        if len(chunk) > max_output_bytes or not decomp_bz.eof:
            raise DecompressionLimitExceeded(
                f"decompression output exceeded limit ({max_output_bytes} bytes)"
            )
        return chunk

    if fmt == CompressionFormat.XZ:
        decomp_xz = lzma.LZMADecompressor()
        chunk = decomp_xz.decompress(data, max_output_bytes + 1)
        if len(chunk) > max_output_bytes or not decomp_xz.eof:
            raise DecompressionLimitExceeded(
                f"decompression output exceeded limit ({max_output_bytes} bytes)"
            )
        return chunk

    return bytes(out)


def compression_ratio(
    uncompressed_size: int,
    compressed_size: int,
) -> float:
    """Compute compression ratio: uncompressed / compressed."""
    if compressed_size <= 0:
        return 1.0
    return float(uncompressed_size) / float(compressed_size)


def estimate_entropy(
    data: bytes,
) -> float:
    """Calculate Shannon entropy of byte data in bits per symbol [0.0, 8.0]."""
    if not data:
        return 0.0
    counts: dict[int, int] = {}
    for byte in data:
        counts[byte] = counts.get(byte, 0) + 1
    total = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def compress_stream(
    in_stream: BinaryIO,
    out_stream: BinaryIO,
    format: CompressionFormat = CompressionFormat.GZIP,
) -> int:
    """Compress input stream into output stream. Returns bytes written."""
    total_written = 0
    if format == CompressionFormat.GZIP:
        with gzip.GzipFile(fileobj=out_stream, mode="wb") as gz:
            while chunk := in_stream.read(65536):
                gz.write(chunk)
                total_written += len(chunk)
    else:
        #? RAW fallback
        while chunk := in_stream.read(65536):
            out_stream.write(chunk)
            total_written += len(chunk)
    return total_written


def decompress_stream(
    in_stream: BinaryIO,
    out_stream: BinaryIO,
    max_bytes: int | None = None,
) -> int:
    """Stream decompression with optional byte bound."""
    header = in_stream.read(16)
    if not header:
        return 0
    combined = io.BytesIO(header + in_stream.read())
    decompressed = decompress_bounded(
    combined.getvalue(),
     max_output_bytes=max_bytes or 100_000_000)
    out_stream.write(decompressed)
    return len(decompressed)


__all__ = [
    "CompressionFormat",
    "DecompressionLimitExceeded",
    "compress_gzip",
    "compress_stream",
    "compress_zlib",
    "compression_ratio",
    "decompress_bounded",
    "decompress_gzip",
    "decompress_stream",
    "decompress_zlib",
    "detect_compression_format",
    "estimate_entropy",
]
