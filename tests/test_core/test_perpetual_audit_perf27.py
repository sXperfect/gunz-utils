"""Phase 27 perpetual audit: round-4 (deepest) re-audit of six core modules.

diagnostics.py, iteration.py, streaming.py, and time_utils.py were verified
correct across targeted probes: exception_dict envelope; chunked/batched/flatten
(off-by-one, max_depth semantics, cycle/deep-nesting guards, generators, set
flattening, dict-as-leaf, scalars); iter_jsonl/write_jsonl round-trip with
non-finite rejection, BoundedWriter/DigestWriter partial-write handling,
copy_and_hash byte-bound truncation, hash_stream chunking; monotonic_deadline/
remaining/expired validation and overflow handling.

One NEW real bug surfaced in sampling.py: ``sample_named_items`` does not
validate ``seed`` upfront. ``stable_priority`` documents ``TypeError`` when
seed is not an integer, and ``sample_named_items`` routes seed only through
``stable_priority`` inside the ``eligible.sort(...)`` key. When there are no
eligible items (empty input, or every item filtered out), the sort key never
runs, so an invalid seed is silently accepted and ``[]`` is returned instead of
raising ``TypeError``. The same call raises ``TypeError`` when eligible items
exist. This is a validation inconsistency: the documented type error depends on
whether any items survive filtering.

This test is expected to be RED against base ``f200992`` for the seed-validation
case and documents the correct behavior after a fix.
"""

from __future__ import annotations

import io

import pytest

from gunz_utils.formatting import format_bytes, format_count, format_duration
from gunz_utils.iteration import batched, chunked, first, flatten
from gunz_utils.sampling import sample_named_items, stable_priority
from gunz_utils.streaming import (
    BoundedWriter,
    copy_and_hash,
    hash_stream,
    iter_jsonl,
    write_jsonl,
)
from gunz_utils.time_utils import expired, monotonic_deadline, remaining


# ---------------------------------------------------------------------------
# RED: sample_named_items must validate `seed` is an int even when there are no
# eligible items. Currently the sort key (which calls stable_priority) never
# runs for an empty eligible list, so a non-int seed is silently accepted and
# [] is returned, contradicting stable_priority's documented TypeError contract
# and the fact that the same call raises TypeError when eligible items exist.
# ---------------------------------------------------------------------------
def test_sample_named_items_seed_validation_consistent() -> None:
    # stable_priority documents TypeError for a non-int seed.
    with pytest.raises(TypeError):
        stable_priority("a", seed="not-an-int")  # type: ignore[arg-type]

    # With eligible items the seed reaches the sort key -> TypeError.
    with pytest.raises(TypeError):
        sample_named_items([("a", 1)], limit=1, seed="not-an-int")  # type: ignore[arg-type]

    # Empty items must behave identically (seed is still invalid), not silently
    # return [].
    with pytest.raises(TypeError):
        sample_named_items([], limit=1, seed="not-an-int")  # type: ignore[arg-type]

    # All items filtered out must also still validate the seed.
    with pytest.raises(TypeError):
        sample_named_items(
            [("a", 1), ("b", 2)],
            limit=1,
            include_patterns=("nomatch",),
            seed="not-an-int",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# GREEN: sampling is otherwise correct.
# ---------------------------------------------------------------------------
def test_sample_named_items_ordering_filtering_and_limits() -> None:
    items = [("z", 0), ("a", 1), ("m", 2)]
    # Deterministic ordering by stable priority then name, limit respected.
    got = sample_named_items(items, limit=2, seed=0)
    assert len(got) == 2
    assert all(name in {"z", "a", "m"} for name, _ in got)
    # Duplicate names are rejected.
    with pytest.raises(ValueError):
        sample_named_items([("a", 1), ("a", 2)], limit=10)
    # include/exclude filtering.
    assert sample_named_items(items, limit=10, include_patterns=("a*",)) == [("a", 1)]
    assert sorted(sample_named_items(items, limit=10, exclude_patterns=("z*",))) == [
        ("a", 1),
        ("m", 2),
    ]
    # limit=0 -> empty; negative limit rejected.
    assert sample_named_items(items, limit=0) == []
    with pytest.raises(ValueError):
        sample_named_items(items, limit=-1)


# ---------------------------------------------------------------------------
# GREEN: formatting canonical zero and negative handling.
# ---------------------------------------------------------------------------
def test_format_duration_zero_and_negative() -> None:
    # Canonical zero representation (per the negative-suppression code path and
    # the maintained test suite) is "0ms".
    assert format_duration(0) == "0ms"
    assert format_duration(-0.0001) == "0ms"  # sign suppressed on zero magnitude
    assert format_duration(0.5) == "500ms"
    assert format_duration(-0.5) == "-500ms"
    assert format_duration(45.6) == "45.6s"
    assert format_duration(-30) == "-30.0s"
    assert format_duration(3661) == "1h 1m 1s"


def test_format_bytes_and_count() -> None:
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(1024, binary=True) == "1.0 KiB"
    assert format_bytes(-1536) == "-1.5 KB"
    assert format_bytes(-0.5) == "0 B"
    assert format_count(0) == "0"
    assert format_count(1500) == "1.5K"
    assert format_count(1_234_567) == "1.2M"
    assert format_count(-1500) == "-1.5K"


# ---------------------------------------------------------------------------
# GREEN: iteration helpers (off-by-one, boundaries, guards).
# ---------------------------------------------------------------------------
def test_iteration_boundaries_and_guards() -> None:
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [(1, 2), (3, 4), (5,)]
    assert list(batched([1, 2, 3], 2)) == [[1, 2], [3]]
    assert list(chunked([], 3)) == []
    with pytest.raises(ValueError):
        list(chunked([1, 2, 3], 0))
    with pytest.raises(ValueError):
        list(chunked([1, 2, 3], True))
    assert list(flatten([[1, [2, [3]]]], max_depth=2)) == [1, 2, [3]]
    assert list(flatten([[1, [2, [3]]]], max_depth=0)) == [[1, [2, [3]]]]
    assert first([1, 2, 3]) == 1
    assert first([], default=42) == 42
    # cycle guard
    cyc: list = []
    cyc.append(cyc)
    with pytest.raises(ValueError):
        list(flatten(cyc))
    # deep-nesting guard
    deep: list = []
    cur = deep
    for _ in range(300):
        nxt: list = []
        cur.append(nxt)
        cur = nxt
    with pytest.raises(ValueError):
        list(flatten(deep, max_nesting=256))


# ---------------------------------------------------------------------------
# GREEN: streaming round-trip, non-finite rejection, byte bounds.
# ---------------------------------------------------------------------------
def test_streaming_jsonl_roundtrip_and_nonfinite_rejection() -> None:
    buf = io.StringIO()
    assert write_jsonl(buf, [{"a": 1.5}, {"c": None}, 3]) == 3
    buf.seek(0)
    assert list(iter_jsonl(buf)) == [{"a": 1.5}, {"c": None}, 3]
    with pytest.raises(ValueError):
        list(iter_jsonl(io.StringIO('{"x": 1e400}\n')))


def test_streaming_copy_and_hash_bounds() -> None:
    out = io.BytesIO()
    res = copy_and_hash(
        io.BytesIO(b"hello world this is a long stream"),
        out,
        max_bytes=5,
        chunk_size=4,
    )
    assert res.bytes_written == 5
    assert out.getvalue() == b"hello"
    # BoundedWriter rejects overflow.
    bw = BoundedWriter(io.BytesIO(), max_bytes=5)
    assert bw.write(b"12345") == 5
    with pytest.raises(ValueError):
        bw.write(b"x")
    # hash_stream deterministic across chunk sizes.
    assert hash_stream(io.BytesIO(b"hello"), chunk_size=1) == hash_stream(
        io.BytesIO(b"hello"), chunk_size=1 << 20
    )


# ---------------------------------------------------------------------------
# GREEN: time_utils validation and monotonic behavior.
# ---------------------------------------------------------------------------
def test_time_utils_validation_and_deadline() -> None:
    for bad in (10**400, float("inf"), float("nan"), -1, True, "x"):
        with pytest.raises(ValueError):
            monotonic_deadline(bad)  # type: ignore[arg-type]
    d = monotonic_deadline(10.0)
    assert remaining(d) > 0.0
    assert not expired(d)
    assert expired(d - 1000.0)
    assert remaining(d - 1000.0) == 0.0
