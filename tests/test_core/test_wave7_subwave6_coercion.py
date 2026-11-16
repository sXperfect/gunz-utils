"""Tests for Wave 7 Sub-Wave 6: Dynamic Schema Coercion & Type Normalization."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from pathlib import Path

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.coercion import (
    CoercionError,
    coerce_bool,
    coerce_float,
    coerce_int,
    coerce_mapping,
    coerce_path,
    coerce_sequence,
    format_coercion_error,
)


def test_coerce_primitives():
    assert coerce_bool("yes") is True
    assert coerce_bool("0") is False
    assert coerce_bool(1) is True

    with pytest.raises(CoercionError):
        coerce_bool("unknown")

    assert coerce_int("42") == 42
    assert coerce_int(42.0) == 42
    with pytest.raises(CoercionError):
        coerce_int(True)  #? rejects bool as int

    assert coerce_float("3.14") == 3.14
    with pytest.raises(CoercionError):
        coerce_float("nan")  #? rejects nan by default

    assert coerce_path("/tmp/test") == Path("/tmp/test")


def test_coerce_sequence_and_mapping():
    seq = coerce_sequence(int, ["1", "2", 3, 4.0])
    assert seq == [1, 2, 3, 4]

    schema = {
        "name": str,
        "age": int,
        "active": bool,
    }
    data = {
        "name": "Alice",
        "age": "30",
        "active": "yes",
        "extra": "ignore_me",
    }
    coerced = coerce_mapping(schema, data, strict=False)
    assert coerced["name"] == "Alice"
    assert coerced["age"] == 30
    assert coerced["active"] is True
    assert coerced["extra"] == "ignore_me"


def test_coercion_error_format():
    schema = {"count": int}
    with pytest.raises(CoercionError) as exc_info:
        coerce_mapping(schema, {"count": "invalid"})

    msg = format_coercion_error(exc_info.value)
    assert "count" in msg
