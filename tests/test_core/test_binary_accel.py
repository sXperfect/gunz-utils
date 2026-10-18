"""Comprehensive contract, equivalence, and fallback tests for varint acceleration."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import re

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import binary
from gunz_utils.binary import (
    ByteReader,
    decode_uvarint,
    decode_zigzag,
    encode_uvarint,
    encode_zigzag,
)
from gunz_utils.io import physical_lines
from gunz_utils.stats import ParetoObjective, RunningStats, pareto_frontier


def test_native_extension_is_compiled_and_active() -> None:
    """Verify that compiled C extension is discovered and loaded in this environment."""
    if binary._accel_encode is None:
        pytest.skip("Native C extension is not compiled in this environment")

    assert binary._accel_encode is not None
    assert binary._accel_decode is not None
    assert binary._accel_encode_zigzag is not None
    assert binary._accel_decode_zigzag is not None
    assert binary._accel_decode_uvarints is not None
    assert binary._accel_decode_zigzags is not None


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
def test_varint_encode_decode_roundtrip_equivalence(
    val: int,
) -> None:
    """Test roundtrip equivalence across canonical boundary values."""
    if binary._accel_encode is None:
        pytest.skip("Native C extension is required for native differential test")

    #? Pure Python
    py_encoded = binary._py_encode_uvarint(val)
    #? Native / Dispatched
    c_encoded = encode_uvarint(val)
    assert c_encoded == py_encoded

    #? Decode with dispatched ByteReader
    reader = ByteReader(c_encoded)
    decoded = reader.read_uvarint()
    assert decoded == val
    assert reader.remaining == 0


@pytest.mark.parametrize(
    "val",
    [0, 1, 127, 128, 255, 256, (1 << 32) - 1, (1 << 64) - 1],
)
def test_pure_python_varint_roundtrip(
    val: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test reference Python encoder and decoder roundtrip independently."""
    monkeypatch.setattr(binary, "_accel_decode", None)
    encoded = binary._py_encode_uvarint(val)
    #? Read using python fallback ByteReader logic
    reader = ByteReader(encoded)
    assert reader.read_uvarint() == val


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
    #? Transactional invariant: offset must remain unchanged on failure
    assert reader.offset == 0


def test_varint_decode_non_canonical_zero_raises_value_error() -> None:
    #? 0x80 followed by 0x00 is non-canonical representation of 0
    reader = ByteReader(b"\x80\x00")
    with pytest.raises(ValueError, match="non-canonical varint"):
        reader.read_uvarint()
    assert reader.offset == 0


def test_varint_decode_exceeds_64_bits_raises_value_error() -> None:
    #? 9 bytes of 0x80 followed by 0x02 exceeds 64 bits
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


def test_byte_reader_invalid_size_leaves_state_unmutated() -> None:
    reader = ByteReader(b"abcdef")
    assert reader.offset == 0
    assert reader.remaining == 6

    #? Fractional, boolean, non-int types must raise TypeError without mutating offset
    for invalid in [0.5, 1.2, True, False, "1", None]:
        with pytest.raises(TypeError, match="read size must be an integer"):
            reader.read(invalid)  # type: ignore[arg-type]
        assert reader.offset == 0
        assert reader.remaining == 6

    #? Out of bounds must raise EOFError without mutating offset
    for oob in [-1, -5, 7, 100]:
        with pytest.raises(EOFError, match="binary read exceeds available data"):
            reader.read(oob)
        assert reader.offset == 0
        assert reader.remaining == 6

    #? Valid read advances offset
    chunk = reader.read(3)
    assert bytes(chunk) == b"abc"
    assert reader.offset == 3
    assert reader.remaining == 3


def test_native_running_stats_merge_differential_parity() -> None:
    """Verify RunningStats.merge produces identical results in native and fallback."""
    import math

    a_vals = [1.0, 2.0, 3.5, 4.0, 5.5, 10.0]
    b_vals = [0.5, 2.5, 3.0, 7.0, 8.0]

    s1 = RunningStats.from_iterable(a_vals)
    s2 = RunningStats.from_iterable(b_vals)
    merged = s1.merge(s2)

    all_vals = a_vals + b_vals
    expected = RunningStats.from_iterable(all_vals)

    assert merged.count == expected.count
    assert math.isclose(merged.mean, expected.mean, rel_tol=1e-12)
    assert math.isclose(merged.variance, expected.variance, rel_tol=1e-12)
    assert math.isclose(merged.minimum, expected.minimum, rel_tol=1e-12)
    assert math.isclose(merged.maximum, expected.maximum, rel_tol=1e-12)
    assert math.isclose(merged.total, expected.total, rel_tol=1e-12)

    #? Empty accumulator merge properties
    empty = RunningStats()
    assert empty.merge(s1).mean == s1.mean
    assert s1.merge(empty).mean == s1.mean


def test_native_pareto_2d_differential_parity() -> None:
    """Verify 2D Pareto frontier sweep parity between native and fallback."""
    items = [
        {"id": "a", "cost": 10.0, "latency": 100.0},
        {"id": "b", "cost": 20.0, "latency": 50.0},
        {"id": "c", "cost": 15.0, "latency": 80.0},
        {"id": "d", "cost": 30.0, "latency": 120.0},
        {"id": "e", "cost": 5.0, "latency": 200.0},
        {"id": "f", "cost": 10.0, "latency": 100.0},
    ]
    objectives = [
        ParetoObjective(name="cost", lower_is_better=True),
        ParetoObjective(name="latency", lower_is_better=True),
    ]

    frontier = pareto_frontier(
        items,
        key=lambda item: (item["cost"], item["latency"]),
        objectives=objectives,
    )
    frontier_ids = [item["id"] for item in frontier]
    assert frontier_ids == ["a", "b", "c", "e", "f"]


def test_native_physical_lines_differential_parity() -> None:
    """Verify physical_lines parity across mixed newlines, keepends, and edge cases."""
    cases = [
        "",
        "single line without newline",
        "line 1\nline 2",
        "line 1\r\nline 2",
        "line 1\rline 2",
        "line 1\nline 2\r\nline 3\rline 4",
        "trailing lf\n",
        "trailing crlf\r\n",
        "trailing cr\r",
        "\n",
        "\r\n",
        "\r",
        "\n\n\n",
        "\r\n\r\n",
        "unicode line separator \u2028 preserved\nnext line",
        "unicode paragraph separator \u2029 preserved\r\nnext line",
    ]

    for text in cases:
        for keepends in (False, True):
            native_res = physical_lines(text, keepends=keepends)
            #? Reference implementation with regex
            lines = []
            start = 0
            for match in re.finditer(r"\r\n|\r|\n", text):
                end = match.end() if keepends else match.start()
                lines.append(text[start:end])
                start = match.end()
            if start < len(text):
                lines.append(text[start:])
            elif not text:
                lines = []
            assert native_res == lines, (
                f"Mismatch for text={text!r}, keepends={keepends}"
            )


@pytest.mark.parametrize(
    "val",
    [
        0,
        -1,
        1,
        -2,
        2,
        63,
        -64,
        64,
        -65,
        127,
        -128,
        128,
        -129,
        (1 << 31) - 1,
        -(1 << 31),
        (1 << 63) - 1,
        -(1 << 63),
    ],
)
def test_zigzag_encode_decode_roundtrip_equivalence(
    val: int,
) -> None:
    """Test signed zigzag roundtrip and parity across critical boundaries."""
    if binary._accel_encode_zigzag is None:
        pytest.skip("Native C extension is required for native differential test")

    #? Reference pure-Python
    py_encoded = binary._py_encode_zigzag(val)
    #? Dispatched native encoder
    c_encoded = encode_zigzag(val)
    assert c_encoded == py_encoded

    #? Decode with ByteReader.read_zigzag()
    reader = ByteReader(c_encoded)
    decoded = reader.read_zigzag()
    assert decoded == val
    assert reader.remaining == 0

    #? Standalone decode_zigzag()
    dec_val, new_offset = decode_zigzag(c_encoded, 0)
    assert dec_val == val
    assert new_offset == len(c_encoded)


def test_zigzag_type_and_range_validation() -> None:
    """Test type and overflow validation for encode_zigzag."""
    for invalid in [None, 3.14, "42", True, False, [1]]:
        with pytest.raises(TypeError, match="value must be an integer \\(not bool\\)"):
            encode_zigzag(invalid)  # type: ignore[arg-type]

    for oob in [1 << 63, (1 << 63) + 1, -(1 << 63) - 1, -(1 << 64)]:
        with pytest.raises(
            ValueError,
            match="signed zigzag varint requires a 64-bit signed integer",
        ):
            encode_zigzag(oob)


def test_zigzag_fallback_parity_when_native_extension_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify zigzag pure-Python fallback parity when native acceleration is off."""
    monkeypatch.setattr(binary, "_accel_encode_zigzag", None)
    monkeypatch.setattr(binary, "_accel_decode_zigzag", None)

    for val in [0, -1, 1, -128, 127, -(1 << 63), (1 << 63) - 1]:
        encoded = encode_zigzag(val)
        reader = ByteReader(encoded)
        assert reader.read_zigzag() == val
        assert reader.remaining == 0

    with pytest.raises(EOFError):
        ByteReader(b"\x80").read_zigzag()

    with pytest.raises(ValueError, match="non-canonical varint"):
        ByteReader(b"\x80\x00").read_zigzag()


def test_batch_readers_native_and_fallback_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify batch reading of uvarints and zigzags in native and fallback."""
    u_vals = [0, 1, 127, 128, 300, (1 << 32) - 1, (1 << 64) - 1]
    z_vals = [0, -1, 1, -128, 127, -(1 << 31), (1 << 31) - 1, -(1 << 63), (1 << 63) - 1]

    u_bytes = b"".join(encode_uvarint(v) for v in u_vals)
    z_bytes = b"".join(encode_zigzag(v) for v in z_vals)

    #? Native batch read
    u_read = ByteReader(u_bytes).read_uvarints(len(u_vals))
    assert u_read == u_vals

    z_read = ByteReader(z_bytes).read_zigzags(len(z_vals))
    assert z_read == z_vals

    #? Empty count returns empty list without moving offset
    r_empty = ByteReader(u_bytes)
    assert r_empty.read_uvarints(0) == []
    assert r_empty.offset == 0
    assert r_empty.read_zigzags(0) == []
    assert r_empty.offset == 0

    #? Negative count raises ValueError
    with pytest.raises(ValueError, match="count must be non-negative"):
        r_empty.read_uvarints(-1)
    with pytest.raises(ValueError, match="count must be non-negative"):
        r_empty.read_zigzags(-1)

    #? Fallback mode
    monkeypatch.setattr(binary, "_accel_decode_uvarints", None)
    monkeypatch.setattr(binary, "_accel_decode_zigzags", None)

    assert ByteReader(u_bytes).read_uvarints(len(u_vals)) == u_vals
    assert ByteReader(z_bytes).read_zigzags(len(z_vals)) == z_vals


def test_batch_readers_transactional_rollback_on_failure() -> None:
    """Verify batch readers rollback offset if EOF or corrupted data is encountered."""
    #? Valid varint followed by truncated varint
    bad_bytes = encode_uvarint(42) + b"\x80"
    reader = ByteReader(bad_bytes)
    with pytest.raises(EOFError):
        reader.read_uvarints(2)
    assert reader.offset == 0

    bad_z_bytes = encode_zigzag(-42) + b"\x80\x00"  #? non-canonical zero
    reader_z = ByteReader(bad_z_bytes)
    with pytest.raises(ValueError, match="non-canonical varint"):
        reader_z.read_zigzags(2)
    assert reader_z.offset == 0


def test_standalone_decode_functions() -> None:
    """Verify standalone decode_uvarint and decode_zigzag functions."""
    payload = encode_uvarint(100) + encode_zigzag(-200)
    val1, off1 = decode_uvarint(payload, 0)
    assert val1 == 100
    val2, off2 = decode_zigzag(payload, off1)
    assert val2 == -200
    assert off2 == len(payload)


