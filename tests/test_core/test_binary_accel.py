"""Comprehensive contract, equivalence, and fallback tests for varint acceleration."""

from __future__ import annotations

import pytest

from gunz_utils import binary
from gunz_utils.binary import ByteReader, encode_uvarint


def test_native_extension_is_compiled_and_active() -> None:
    """Verify that compiled C extension is discovered and loaded in this environment."""
    if binary._accel_encode is None:
        pytest.skip("Native C extension is not compiled in this environment")

    assert binary._accel_encode is not None
    assert binary._accel_decode is not None


def test_varint_encode_keyword_argument_parity() -> None:
    """Verify encode_uvarint accepts 'value' keyword argument identically."""
    assert encode_uvarint(value=42) == encode_uvarint(42)
    assert encode_uvarint(value=0) == b"\x00"
    assert encode_uvarint(value=128) == b"\x80\x01"


@pytest.mark.parametrize(
    "val",
    [
        0,
        1,
        2,
        63,
        64,
        127,
        128,
        129,
        255,
        256,
        16383,
        16384,
        2097151,
        2097152,
        268435455,
        268435456,
        (1 << 32) - 1,
        1 << 32,
        (1 << 63) - 1,
        1 << 63,
        (1 << 64) - 1,
    ],
)
def test_varint_encode_decode_roundtrip_equivalence(val: int) -> None:
    """Test roundtrip equivalence across canonical boundary values."""
    # Pure Python
    py_encoded = binary._py_encode_uvarint(val)
    # Native / Dispatched
    c_encoded = encode_uvarint(val)
    assert c_encoded == py_encoded

    # Decode with dispatched ByteReader
    reader = ByteReader(c_encoded)
    decoded = reader.read_uvarint()
    assert decoded == val
    assert reader.remaining == 0


def test_varint_encode_negative_raises_value_error() -> None:
    for neg in [-1, -2, -100, -(1 << 32), -(1 << 64)]:
        with pytest.raises(
            ValueError, match="unsigned varint requires a 64-bit unsigned integer"
        ):
            encode_uvarint(neg)


def test_varint_encode_overflow_raises_value_error() -> None:
    for overflow in [1 << 64, (1 << 64) + 1, 1 << 65, 1 << 128]:
        with pytest.raises(
            ValueError, match="unsigned varint requires a 64-bit unsigned integer"
        ):
            encode_uvarint(overflow)


def test_varint_decode_truncated_raises_eof() -> None:
    reader = ByteReader(b"\x80")
    with pytest.raises(EOFError, match="binary read exceeds available data"):
        reader.read_uvarint()
    # Transactional invariant: offset must remain unchanged on failure
    assert reader.offset == 0


def test_varint_decode_non_canonical_zero_raises_value_error() -> None:
    # 0x80 followed by 0x00 is non-canonical representation of 0
    reader = ByteReader(b"\x80\x00")
    with pytest.raises(ValueError, match="non-canonical varint"):
        reader.read_uvarint()
    assert reader.offset == 0


def test_varint_decode_exceeds_64_bits_raises_value_error() -> None:
    # 9 bytes of 0x80 followed by 0x02 exceeds 64 bits
    reader = ByteReader(b"\x80" * 9 + b"\x02")
    with pytest.raises(ValueError, match="varint exceeds 64 bits"):
        reader.read_uvarint()
    assert reader.offset == 0


def test_varint_fallback_parity_when_native_extension_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify identical behavior when native acceleration is disabled."""
    monkeypatch.setattr(binary, "_accel_decode", None)
    monkeypatch.setattr(binary, "_accel_encode", None)

    for val in [0, 1, 127, 128, 300, (1 << 64) - 1]:
        encoded = encode_uvarint(val)
        reader = ByteReader(encoded)
        assert reader.read_uvarint() == val
        assert reader.remaining == 0

    with pytest.raises(EOFError):
        ByteReader(b"\x80").read_uvarint()

    with pytest.raises(ValueError, match="non-canonical varint"):
        ByteReader(b"\x80\x00").read_uvarint()

    with pytest.raises(ValueError, match="varint exceeds 64 bits"):
        ByteReader(b"\x80" * 9 + b"\x02").read_uvarint()


def test_fresh_import_without_native_extension() -> None:
    """Verify fresh import and public APIs work when native extension is unavailable."""
    import importlib
    import sys

    saved_binary = sys.modules.get("gunz_utils.binary")
    saved_accel = sys.modules.get("gunz_utils._accel")
    try:
        sys.modules.pop("gunz_utils.binary", None)
        sys.modules["gunz_utils._accel"] = None  # type: ignore[assignment]

        fresh_binary = importlib.import_module("gunz_utils.binary")
        assert fresh_binary._accel_encode is None
        assert fresh_binary._accel_decode is None

        enc = fresh_binary.encode_uvarint(42)
        assert enc == b"\x2a"
        reader = fresh_binary.ByteReader(enc)
        assert reader.read_uvarint() == 42
    finally:
        if saved_binary is not None:
            sys.modules["gunz_utils.binary"] = saved_binary
        else:
            sys.modules.pop("gunz_utils.binary", None)
        if saved_accel is not None:
            sys.modules["gunz_utils._accel"] = saved_accel
        else:
            sys.modules.pop("gunz_utils._accel", None)
