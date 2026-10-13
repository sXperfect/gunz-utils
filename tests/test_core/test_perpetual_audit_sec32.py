"""Perpetual security audit phase 32 (round 4, deepest).

Re-audit of ``buffers``, ``diagnostics``, ``iteration``, ``sampling``, and
``streaming``.

Findings:

1. ``streaming.iter_jsonl`` does not apply the package's shared JSON
   nesting-depth bound (streaming.py:83-87).

   ``iter_jsonl`` calls the standard-library ``json.loads`` directly on each
   line without bounding nesting depth, unlike ``serialization.json_loads``
   which enforces ``_MAX_JSON_DEPTH = 100`` (serialization.py:39, 245-251).
   As a result a single JSON Lines record nested deeper than the package's
   encode-side bound (``canonical_json``/``json_dumps``/``fingerprint`` reject
   records nested past 100 levels) is silently *accepted* by ``iter_jsonl`` --
   an asymmetric validation gap -- and a record nested deeply enough (about
   80k levels) raises a raw ``RecursionError`` (a ``RuntimeError`` subclass)
   instead of the documented ``ValueError``.  This directly contradicts the
   module's own stack-safety intent: ``_reject_nonfinite`` (streaming.py:40-60)
   is explicitly iterative "so deep records do not overflow the interpreter
   stack", but the preceding ``json.loads`` call defeats that guarantee.
   Correct behavior: bound nesting depth and raise ``ValueError`` for
   over-deep records, matching ``serialization.json_loads``.

2. ``sampling.sample_named_items`` / ``sampling.stable_priority`` accept a
   boolean ``seed``, silently coercing it to 0/1, while the sibling numeric
   parameter ``limit`` rejects booleans (sampling.py:91-102).

   ``sample_named_items`` validates ``limit`` with an explicit boolean guard
   (``isinstance(limit, bool) or not isinstance(limit, int)`` ->
   ``ValueError``) but validates ``seed`` only with ``isinstance(seed, int)``
   (sampling.py:101-102), which admits booleans because ``bool`` subclasses
   ``int``.  ``stable_priority`` likewise checks ``isinstance(seed, int)``
   (sampling.py:47-48) and accepts ``seed=True``/``False``.  Every other
   numeric configuration parameter in the package rejects booleans explicitly
   (``limit``, ``n``, ``chunk_size``, ``max_bytes``, ``fanout_levels`` ...).
   A boolean seed is silently reinterpreted as 0/1 instead of being rejected,
   which is an inconsistent validation boundary.  Correct behavior: reject a
   boolean seed (consistent with ``limit``), so a caller cannot silently pass
   a wrong-typed seed.
"""

import io

import pytest

from gunz_utils import buffers, diagnostics, iteration, sampling, streaming

# ---------------------------------------------------------------------------
# Finding 1: iter_jsonl does not bound JSON nesting depth
# ---------------------------------------------------------------------------


def test_iter_jsonl_applies_nesting_depth_bound():
    """RED: a record nested deeper than the package's shared encode-side bound
    (100) must be rejected.  Currently ``iter_jsonl`` accepts a 101-deep
    record that ``serialization.json_loads``/``canonical_json`` reject.
    """
    with pytest.raises(ValueError):
        list(streaming.iter_jsonl(io.StringIO("[" * 101 + "]" * 101)))


def test_iter_jsonl_rejects_deep_record_with_valueerror_not_recursionerror():
    """RED: an extremely deep record must raise ValueError, not the raw
    RecursionError (a RuntimeError) that ``json.loads`` currently surfaces,
    contradicting the documented ``Raises ValueError`` contract.
    """
    with pytest.raises(ValueError):
        list(streaming.iter_jsonl(io.StringIO("[" * 80000 + "]" * 80000)))


# ---------------------------------------------------------------------------
# Finding 2: sample_named_items / stable_priority accept a boolean seed
# ---------------------------------------------------------------------------


def test_sample_named_items_rejects_boolean_seed():
    """RED: a boolean seed must be rejected (consistent with ``limit``, which
    rejects booleans).  Currently ``seed=True``/``False`` are silently coerced
    to 0/1.
    """
    with pytest.raises((TypeError, ValueError)):
        sampling.sample_named_items([("a", 1)], limit=None, seed=True)
    with pytest.raises((TypeError, ValueError)):
        sampling.sample_named_items([("a", 1)], limit=None, seed=False)


def test_stable_priority_rejects_boolean_seed():
    """RED: ``stable_priority`` must also reject a boolean seed instead of
    silently treating it as 0/1.
    """
    with pytest.raises((TypeError, ValueError)):
        sampling.stable_priority("item", seed=True)


# ---------------------------------------------------------------------------
# GREEN: streaming correctness that must not regress
# ---------------------------------------------------------------------------


def test_iter_jsonl_rejects_nonstandard_and_nonfinite():
    """GREEN: non-standard constants and non-finite numbers are rejected with
    ValueError (the documented contract) for ordinary-depth records.
    """
    with pytest.raises(ValueError):
        list(streaming.iter_jsonl(io.StringIO("NaN")))
    with pytest.raises(ValueError):
        list(streaming.iter_jsonl(io.StringIO('{"x": 1e400}')))


def test_iter_jsonl_yields_valid_records():
    """GREEN: valid JSON Lines records decode in order; blank lines are skipped."""
    handle = io.StringIO('{"a": 1}\n\n{"b": 2}\n')
    assert list(streaming.iter_jsonl(handle)) == [{"a": 1}, {"b": 2}]


def test_write_jsonl_round_trip():
    """GREEN: write_jsonl produces compact records that iter_jsonl decodes."""
    out = io.StringIO()
    count = streaming.write_jsonl(out, [{"a": 1}, {"b": [1, 2, 3]}])
    assert count == 2
    assert list(streaming.iter_jsonl(io.StringIO(out.getvalue()))) == [
        {"a": 1},
        {"b": [1, 2, 3]},
    ]


def test_bounded_writer_enforces_limit():
    """GREEN: BoundedWriter rejects writes that exceed its cumulative limit and
    handles partial underlying writes.
    """
    out = io.BytesIO()
    writer = streaming.BoundedWriter(out, max_bytes=5)
    writer.write(b"abc")
    assert writer.bytes_written == 3
    with pytest.raises(ValueError):
        writer.write(b"def")
    assert writer.bytes_written == 3
    assert out.getvalue() == b"abc"


def test_digest_writer_truncates_and_hashes():
    """GREEN: DigestWriter truncates at max_bytes and hashes only written bytes."""
    import hashlib

    out = io.BytesIO()
    writer = streaming.DigestWriter(out, max_bytes=4)
    writer.write(b"abcdef")
    assert writer.bytes_written == 4
    assert out.getvalue() == b"abcd"
    assert writer.hexdigest == hashlib.sha256(b"abcd").hexdigest()


def test_copy_and_hash_bounds_output():
    """GREEN: copy_and_hash stops pulling from an oversized source at max_bytes."""
    out = io.BytesIO()
    result = streaming.copy_and_hash(io.BytesIO(b"x" * 1000), out, max_bytes=10)
    assert result.bytes_written == 10
    assert len(out.getvalue()) == 10


def test_hash_stream_and_fingerprint_deterministic():
    """GREEN: hash_stream hashes a stream; fingerprint is deterministic."""
    assert streaming.hash_stream(io.BytesIO(b"abc")) == streaming.hash_stream(
        io.BytesIO(b"abc")
    )
    assert streaming.fingerprint({"b": 1, "a": 2}) == streaming.fingerprint(
        {"a": 2, "b": 1}
    )


# ---------------------------------------------------------------------------
# GREEN: sampling determinism and validation that must not regress
# ---------------------------------------------------------------------------


def test_stable_priority_deterministic_and_seed_sensitive():
    """GREEN: stable_priority is deterministic and differs across seeds."""
    assert sampling.stable_priority("name", seed=0) == sampling.stable_priority(
        "name", seed=0
    )
    assert sampling.stable_priority("name", seed=1) != sampling.stable_priority(
        "name", seed=2
    )


def test_sample_named_items_limit_semantics():
    """GREEN: limit=0 returns empty; limit slices deterministically."""
    items = [("a", 1), ("b", 2), ("c", 3)]
    assert sampling.sample_named_items(items, limit=0) == []
    assert len(sampling.sample_named_items(items, limit=2)) == 2


def test_sample_named_items_rejects_duplicate_and_bad_types():
    """GREEN: duplicate names, non-str names, and non-int seeds are rejected."""
    with pytest.raises(ValueError):
        sampling.sample_named_items([("a", 1), ("a", 2)], limit=None)
    with pytest.raises(TypeError):
        sampling.sample_named_items([(1, 1)], limit=None)  # type: ignore[list-item]
    with pytest.raises(TypeError):
        sampling.sample_named_items([("a", 1)], limit=None, seed="x")
    with pytest.raises(ValueError):
        sampling.sample_named_items([("a", 1)], limit=True)  # type: ignore[arg-type]


def test_sample_named_items_glob_filtering():
    """GREEN: include/exclude glob patterns filter deterministically."""
    items = [("a.log", 1), ("b.json", 2), ("c.log", 3)]
    assert [n for n, _ in sampling.sample_named_items(
        items, limit=None, include_patterns=("*.log",)
    )] == ["c.log", "a.log"]
    assert [n for n, _ in sampling.sample_named_items(
        items, limit=None, exclude_patterns=("*.log",)
    )] == ["b.json"]


# ---------------------------------------------------------------------------
# GREEN: iteration boundaries, cycles, and depth that must not regress
# ---------------------------------------------------------------------------


def test_chunked_and_batched_boundaries():
    """GREEN: partial final groups are preserved; n validation is strict."""
    assert list(iteration.chunked([1, 2, 3, 4, 5], 2)) == [(1, 2), (3, 4), (5,)]
    assert list(iteration.batched([1, 2, 3], 2)) == [[1, 2], [3]]
    with pytest.raises(ValueError):
        list(iteration.chunked([1], 0))
    with pytest.raises(ValueError):
        list(iteration.chunked([1], True))  # type: ignore[arg-type]


def test_flatten_cycle_detection():
    """GREEN: a self-referential structure raises ValueError, not an infinite loop."""
    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(ValueError):
        list(iteration.flatten([cycle]))


def test_flatten_bounds_deep_nesting():
    """GREEN: deeply nested acyclic input raises ValueError (bounded), not
    RecursionError or an uncontrolled runaway.
    """
    deep: object = 1
    for _ in range(1000):
        deep = [deep]
    with pytest.raises(ValueError):
        list(iteration.flatten(deep))  # type: ignore[arg-type]


def test_flatten_max_depth_semantics():
    """GREEN: max_depth controls descent level (Lodash semantics)."""
    assert list(iteration.flatten([[1, [2, [3]]]], max_depth=1)) == [1, [2, [3]]]
    assert list(iteration.flatten([[1, [2, [3]]]], max_depth=2)) == [1, 2, [3]]
    assert list(iteration.flatten([[1, 2]], max_depth=0)) == [[1, 2]]


def test_first_returns_default_on_empty():
    """GREEN: first() returns the default for empty input and the item otherwise."""
    assert iteration.first([], default="missing") == "missing"
    assert iteration.first([7, 8]) == 7


# ---------------------------------------------------------------------------
# GREEN: buffers and diagnostics that must not regress
# ---------------------------------------------------------------------------


def test_as_readonly_view_correct_and_readonly():
    """GREEN: as_readonly_view returns a byte-oriented readonly view, handles
    stepped (non-contiguous) views via a copy, and rejects non-bytes-like input.
    """
    assert bytes(buffers.as_readonly_view(b"abc")) == b"abc"
    stepped = buffers.as_readonly_view(memoryview(b"abcdef")[::2])
    assert bytes(stepped) == b"ace"
    assert stepped.readonly is True
    with pytest.raises(TypeError):
        buffers.as_readonly_view("abc")  # type: ignore[arg-type]


def test_exception_dict_redacts_and_excludes_message():
    """GREEN: exception_dict redacts secret context and excludes the raw message
    by default; include_message is an explicit opt-in and must be bool.
    """
    result = diagnostics.exception_dict(
        RuntimeError("boom"),
        context={"token": "SECRET", "user_id": 12345},
    )
    assert result["type"] == "RuntimeError"
    assert "message" not in result
    assert result["context"]["token"] == "****"
    opted = diagnostics.exception_dict(RuntimeError("boom"), include_message=True)
    assert opted["message"] == "boom"
    with pytest.raises(TypeError):
        diagnostics.exception_dict(RuntimeError("boom"), include_message="yes")  # type: ignore[arg-type]
