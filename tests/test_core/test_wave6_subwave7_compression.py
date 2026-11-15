"""Tests for Wave 6 Sub-Wave 7: Compression Magic Bytes & Bounded Decompression."""

import pytest

from gunz_utils.compression import (
    CompressionFormat,
    DecompressionLimitExceeded,
    compress_gzip,
    compress_zlib,
    compression_ratio,
    decompress_bounded,
    decompress_gzip,
    decompress_zlib,
    detect_compression_format,
    estimate_entropy,
)


def test_magic_byte_detection():
    data = b"Hello world! This is a test string."
    gz = compress_gzip(data)
    zl = compress_zlib(data)

    assert detect_compression_format(gz) == CompressionFormat.GZIP
    assert detect_compression_format(zl) == CompressionFormat.ZLIB
    assert detect_compression_format(b"RAW DATA") == CompressionFormat.RAW


def test_bounded_decompression_and_roundtrip():
    data = b"Repeat" * 1000
    gz = compress_gzip(data)

    decomp = decompress_gzip(gz)
    assert decomp == data

    # Exceed limit
    with pytest.raises(DecompressionLimitExceeded):
        decompress_bounded(gz, max_output_bytes=50)


def test_compression_ratio_and_entropy():
    data = b"AAAAAAAAAA"
    # Low entropy for repetitive bytes
    ent = estimate_entropy(data)
    assert ent == 0.0

    diverse = bytes(range(256))
    ent_div = estimate_entropy(diverse)
    assert pytest.approx(ent_div, 0.01) == 8.0

    ratio = compression_ratio(1000, 250)
    assert ratio == 4.0
