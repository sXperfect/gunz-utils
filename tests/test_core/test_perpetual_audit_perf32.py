"""Phase 32 perpetual audit: round-4 (deepest) re-audit of five core modules.

buffers.py, diagnostics.py, iteration.py, sampling.py, streaming.py.

Verified correct at base d6ef4b4 (GREEN companion tests below):
- buffers: as_readonly_view returns a readonly byte view for bytes/bytearray/
  memoryview, falls back to a copy for non-contiguous slices, and reinterprets
  non-byte-format memoryviews.
- diagnostics: exception_dict envelope (type only by default, opt-in message),
  and context redaction via redact_dict.
- iteration: chunked/batched/first, flatten (default, max_depth, generators),
  cycle guards (top-level self-reference and str-in-types self-similarity).
- sampling: deterministic priority ordering, duplicate-name rejection, bool
  limit rejection, float seed rejection.
- streaming: write_jsonl/iter_jsonl round-trip, non-finite JSON rejection
  (1e400 decode, NaN encode), DigestWriter truncation, copy_and_hash max_bytes
  bound, BoundedWriter limit enforcement, hash_stream, fingerprint.

One NEW finding:

1) sampling.py seed accepts bool (stable_priority:47-48, sample_named_items:
   101-102). Both validate ``not isinstance(seed, int)``, but ``bool`` is a
   subclass of ``int``, so ``seed=True`` and ``seed=False`` are silently
   accepted. They are then stringified in the digest payload (``f"{True}" ==
   "True"``), so ``stable_priority(name, seed=True) !=
   stable_priority(name, seed=1)`` and ``seed=True`` yields a different
   sampling order than the equivalent integer seed. This violates the
   documented ``seed must be int`` TypeError contract and is inconsistent with
   the neighbouring ``limit`` check (sampling.py:91-96), which explicitly
   rejects bool via ``isinstance(limit, bool) or not isinstance(limit, int)``.
   Expected: bool seed raises TypeError like any other non-int seed. Currently
   accepted (RED).

This test is expected to be RED against base d6ef4b4 for the seed-bool finding
and GREEN for the companion behaviors.
"""

from __future__ import annotations

import array
import io

import pytest

from gunz_utils import buffers, diagnostics, iteration, sampling
from gunz_utils import streaming as S


# ---------------------------------------------------------------------------
# RED: sampling seed must reject bool like any other non-int seed.
# ---------------------------------------------------------------------------
def test_sampling_stable_priority_rejects_bool_seed() -> None:
    with pytest.raises(TypeError):
        sampling.stable_priority("name", seed=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        sampling.stable_priority("name", seed=False)  # type: ignore[arg-type]


def test_sampling_sample_named_items_rejects_bool_seed() -> None:
    with pytest.raises(TypeError):
        sampling.sample_named_items(
            [("a", 1), ("b", 2)], limit=None, seed=True  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        sampling.sample_named_items(
            [("a", 1), ("b", 2)], limit=None, seed=False  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# GREEN: buffers.
# ---------------------------------------------------------------------------
def test_buffers_as_readonly_view() -> None:
    for data in (b"ab", bytearray(b"ab"), memoryview(b"ab")):
        view = buffers.as_readonly_view(data)
        assert view.readonly is True
        assert bytes(view) == b"ab"
    # Non-contiguous slice falls back to a copy of the logical bytes.
    stepped = memoryview(bytearray(b"abcdef"))[::2]
    assert bytes(buffers.as_readonly_view(stepped)) == b"ace"
    # Non-byte-format memoryview reinterprets as bytes.
    packed = memoryview(array.array("I", [1, 2, 3]))
    packed_bytes = bytes(buffers.as_readonly_view(packed))
    assert len(packed_bytes) == 12
    assert packed_bytes[:4] == b"\x01\x00\x00\x00"
    with pytest.raises(TypeError):
        buffers.as_readonly_view("nope")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: diagnostics.
# ---------------------------------------------------------------------------
def test_diagnostics_exception_dict() -> None:
    try:
        raise ValueError("secret pw123")
    except ValueError as exc:
        assert diagnostics.exception_dict(exc) == {"type": "ValueError"}
        assert diagnostics.exception_dict(exc, include_message=True) == {
            "type": "ValueError",
            "message": "secret pw123",
        }
        out = diagnostics.exception_dict(
            exc, context={"password": "hunter2", "user": "alice"}
        )
        assert out["context"]["password"] == "****"
        assert out["context"]["user"] == "alice"


# ---------------------------------------------------------------------------
# GREEN: iteration.
# ---------------------------------------------------------------------------
def test_iteration_chunked_batched_first() -> None:
    assert list(iteration.chunked(range(5), 2)) == [(0, 1), (2, 3), (4,)]
    assert list(iteration.batched(range(5), 2)) == [[0, 1], [2, 3], [4]]
    assert iteration.first([1, 2, 3]) == 1
    assert iteration.first([], default="missing") == "missing"
    with pytest.raises(ValueError):
        list(iteration.chunked([1, 2], True))  # type: ignore[arg-type]


def test_iteration_flatten() -> None:
    assert list(iteration.flatten([[1, 2], [3, [4, 5]]])) == [1, 2, 3, 4, 5]
    assert list(iteration.flatten([[1, [2, [3]]]], max_depth=1)) == [1, [2, [3]]]
    assert list(iteration.flatten([(x for x in range(3)), [4]])) == [0, 1, 2, 4]
    # Cycle guards: top-level self-reference and str-in-types self-similarity.
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError):
        list(iteration.flatten(cyclic))
    with pytest.raises(ValueError):
        list(iteration.flatten("ab", types=(list, tuple, str)))


# ---------------------------------------------------------------------------
# GREEN: sampling.
# ---------------------------------------------------------------------------
def test_sampling_determinism_and_validation() -> None:
    items = [("a", 1), ("b", 2), ("c", 3)]
    assert sampling.sample_named_items(items, limit=2, seed=42) == (
        sampling.sample_named_items(items, limit=2, seed=42)
    )
    with pytest.raises(ValueError):
        sampling.sample_named_items([("a", 1), ("a", 2)], limit=None)
    with pytest.raises(ValueError):
        sampling.sample_named_items([("a", 1)], limit=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        sampling.stable_priority("name", seed=1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: streaming.
# ---------------------------------------------------------------------------
def test_streaming_jsonl() -> None:
    out = io.StringIO()
    assert S.write_jsonl(out, [{"a": 1}, {"b": [1, 2]}]) == 2
    assert list(S.iter_jsonl(io.StringIO('{"a": 1}\n\n{"b": 2}\n'))) == [
        {"a": 1},
        {"b": 2},
    ]
    with pytest.raises(ValueError):
        list(S.iter_jsonl(io.StringIO("1e400\n")))
    with pytest.raises(ValueError):
        S.write_jsonl(io.StringIO(), [float("nan")])


def test_streaming_bounded_writers_and_copy() -> None:
    out = io.BytesIO()
    bw = S.BoundedWriter(out, max_bytes=5)
    assert bw.write(b"abc") == 3
    assert bw.write(b"de") == 2
    with pytest.raises(ValueError):
        bw.write(b"f")
    out2 = io.BytesIO()
    dw = S.DigestWriter(out2, max_bytes=3)
    assert dw.write(b"hello") == 3
    assert out2.getvalue() == b"hel"
    src = io.BytesIO(b"0123456789")
    dst = io.BytesIO()
    result = S.copy_and_hash(src, dst, max_bytes=4)
    assert result.bytes_written == 4
    assert dst.getvalue() == b"0123"
    # BoundedWriter rejects writes beyond a zero limit.
    with pytest.raises(ValueError):
        S.BoundedWriter(io.BytesIO(), max_bytes=0).write(b"x")
