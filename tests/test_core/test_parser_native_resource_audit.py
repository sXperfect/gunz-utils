"""Finite parser allocation, export lifetime, and optional C reference proofs."""

# gunz-style: ignore-file[GS020]

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import gc
import importlib
import os
import sys
import tracemalloc
import weakref
from typing import Any

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import binary, serialization


class _Buffer(bytearray):
    pass


def _native() -> Any:
    if binary._accel_decode is None:
        pytest.skip("requires asserted compiled native resource audit mode")
    return importlib.import_module("gunz_utils._accel")


def test_backend_provenance_is_explicit_when_matrix_requests_it() -> None:
    hooks = (
        binary._accel_encode,
        binary._accel_decode,
        serialization._accel_is_json_clean,
    )
    expected = os.environ.get("RS03_EXPECT_NATIVE")
    if expected is not None:
        assert all(hook is not None for hook in hooks) is (expected == "1")
    if binary._accel_decode is not None:
        module = _native()
        assert module.has_accel()
        assert module.__file__.endswith((".so", ".pyd"))
        if expected == "1":
            assert "/tmp/" in module.__file__.replace("\\", "/")


@pytest.mark.parametrize(
    "data,error",
    [
        (b"", EOFError),
        (b"\x80", EOFError),
        (b"\x80\0", ValueError),
        (b"\x80" * 9 + b"\x02", ValueError),
    ],
)
def test_binary_failure_releases_exports_when_reader_is_released(
    data: bytes,
    error: type[Exception],
) -> None:
    buffer = _Buffer(data)
    reference = weakref.ref(buffer)
    reader = binary.ByteReader(buffer)
    with pytest.raises(error):
        reader.read_uvarint()
    assert reader.offset == 0
    with pytest.raises(BufferError):
        buffer.extend(b"x")
    del reader
    gc.collect()
    buffer.extend(b"x")
    del buffer
    gc.collect()
    assert reference() is None


def test_retained_read_view_intentionally_pins_export_until_released() -> None:
    buffer = _Buffer(b"abc")
    reference = weakref.ref(buffer)
    reader = binary.ByteReader(buffer)
    view = reader.read(1)
    del reader
    gc.collect()
    with pytest.raises(BufferError):
        buffer.extend(b"x")
    view.release()
    buffer.extend(b"x")
    del view, buffer
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize(
    "data,offset,error",
    [
        (b"", 0, EOFError),
        (b"\x80", 0, EOFError),
        (b"\x80\0", 0, ValueError),
        (b"\x80" * 9 + b"\x02", 0, ValueError),
        (b"\x01", -1, EOFError),
        (b"\x01", 1, EOFError),
        (b"\x01", 1 << 100, OverflowError),
    ],
)
def test_native_decode_error_releases_buffer_export_immediately(
    data: bytes,
    offset: int,
    error: type[Exception],
) -> None:
    native = _native()
    buffer = bytearray(data)
    for _ in range(32):
        with pytest.raises(error):
            native.decode_uvarint(buffer, offset)
        #? Resize proves the acquired Py_buffer export no longer exists.
        buffer.extend(b"x")
        del buffer[-1:]


def test_native_success_and_strided_buffer_failure_do_not_retain_exports() -> None:
    native = _native()
    buffer = bytearray(b"\xff" * 9 + b"\x01")
    for _ in range(128):
        assert native.decode_uvarint(buffer, 0) == ((1 << 64) - 1, 10)
        buffer.extend(b"x")
        del buffer[-1:]
    view = memoryview(buffer)[::2]
    with pytest.raises(BufferError):
        native.decode_uvarint(view, 0)
    view.release()
    buffer.extend(b"x")


def test_native_repeated_calls_restore_input_reference_counts() -> None:
    native = _native()
    clean = {"leaf": [1, "value"]}
    cyclic: list[Any] = []
    cyclic.append(cyclic)

    class Integer(int):
        def __and__(self,
            other: int,
        ) -> int:
            raise ValueError("synthetic subclass failure")

    integer = Integer(129)

    def workload() -> None:
        for _ in range(256):
            assert native.is_json_clean(clean, 100)
            try:
                native.is_json_clean(cyclic, 100)
            except ValueError:
                pass
            else:
                raise AssertionError("cycle depth rejection missing")
            try:
                native.encode_uvarint(integer)
            except ValueError:
                pass
            else:
                raise AssertionError("subclass exception delegation missing")

    workload()
    gc.collect()
    before = tuple(sys.getrefcount(value) for value in (clean, cyclic, integer))
    workload()
    gc.collect()
    after = tuple(sys.getrefcount(value) for value in (clean, cyclic, integer))
    assert after == before


def test_shared_dag_expansion_is_depth_bounded_but_not_count_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    #? A compact caller-owned Python DAG, not a compact decoded JSON document.
    monkeypatch.setattr(serialization, "_accel_is_json_clean", None)
    value: Any = "leaf"
    for _ in range(10):
        value = [value, value]
    tracemalloc.start()
    try:
        result = serialization.to_jsonable(value)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    pending = [result]
    leaves = 0
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
        else:
            assert item == "leaf"
            leaves += 1
    assert leaves == 1024
    assert peak < 2_000_000


def test_repeated_finite_conversion_does_not_retain_unreachable_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    #? Disable optional identity sharing; measure live allocation after warmup/GC.
    monkeypatch.setattr(serialization, "_accel_is_json_clean", None)
    value = [{"x": list(range(32))} for _ in range(8)]

    def workload() -> None:
        for _ in range(128):
            serialization.to_jsonable(value)

    tracemalloc.start()
    try:
        workload()
        gc.collect()
        baseline, _ = tracemalloc.get_traced_memory()
        workload()
        gc.collect()
        retained, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert retained - baseline < 16_384


def test_standard_json_decoder_budgets_and_nonfinite_semantics_are_caller_owned() -> (
    None
):
    decoded = serialization.json_loads("[NaN, Infinity, -Infinity]")
    assert len(decoded) == 3
    with pytest.raises(ValueError, match="Out of range"):
        serialization.canonical_json(decoded)


@pytest.mark.parametrize(
    "budget",
    [-(1 << 100), -(1 << 31) - 1, -1, 0, 1, 128, 129, (1 << 31) - 1, 1 << 31, 1 << 100],
)
def test_depth_integer_budget_has_native_reference_exception_parity(
    monkeypatch: pytest.MonkeyPatch,
    budget: int,
) -> None:
    value = {"leaf": 1}

    def outcome() -> tuple[str, Any]:
        try:
            return "value", serialization.to_jsonable(value, _max_depth=budget)
        except Exception as error:
            return "error", type(error)

    accelerated = outcome()
    monkeypatch.setattr(serialization, "_accel_is_json_clean", None)
    reference = outcome()
    assert accelerated == reference


@pytest.mark.parametrize("budget", [1 << 31, 1 << 100])
def test_large_depth_budget_does_not_become_a_new_public_ceiling(
    monkeypatch: pytest.MonkeyPatch,
    budget: int,
) -> None:
    value: Any = "leaf"
    for _ in range(160):
        value = [value]
    converted = serialization.to_jsonable(value, _max_depth=budget)
    monkeypatch.setattr(serialization, "_accel_is_json_clean", None)
    expected = serialization.to_jsonable(value, _max_depth=budget)
    assert converted == expected


@pytest.mark.parametrize(
    "budget,native_budget", [(100, 100), (128, 128), (1 << 100, 129)]
)
def test_classifier_budget_is_only_an_optimization_boundary(
    monkeypatch: pytest.MonkeyPatch,
    budget: int,
    native_budget: int,
) -> None:
    received: list[int] = []

    def classifier(
        value: Any,
        depth: int,
    ) -> bool:
        received.append(depth)
        return False

    monkeypatch.setattr(serialization, "_accel_is_json_clean", classifier)
    value = {"leaf": 1}
    assert serialization.to_jsonable(value, _max_depth=budget) == value
    assert received == [native_budget]


def test_negative_depth_uses_reference_error_before_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(
        value: Any,
        depth: int,
    ) -> bool:
        raise AssertionError("negative depth must be rejected before classifier")

    monkeypatch.setattr(serialization, "_accel_is_json_clean", forbidden)
    with pytest.raises(ValueError, match="maximum nesting depth"):
        serialization.to_jsonable({"leaf": 1}, _max_depth=-(1 << 100))
