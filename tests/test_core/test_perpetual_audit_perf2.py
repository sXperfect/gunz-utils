"""Perpetual correctness & performance audit regressions (phase 2).

Each test pins a defect found during the round-2 audit of
``gunz_utils.{async_utils,retry,streaming,rate_limit,partitions}``. The tests
currently FAIL against the audited revision (6735052, which includes the
phase-1 fixes); they encode the expected post-fix behavior and should be
un-skipped once the implementation is corrected. Production code is
intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import hashlib
import io

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.partitions import (
    assert_disjoint_partitions,
    partition_overlaps,
)
from gunz_utils.streaming import copy_and_hash, iter_jsonl

# ---------------------------------------------------------------------------
# iter_jsonl: overflowing JSON numeric literals silently decode to +/-inf.
#
# ``iter_jsonl`` rejects the non-standard ``NaN``/``Infinity``/``-Infinity``
# literals via ``parse_constant``, but a standard JSON numeric literal that
# overflows the float range (e.g. ``1e400``) decodes to ``float('inf')``
# without error. ``write_jsonl`` (allow_nan=False) and ``fingerprint`` reject
# non-finite floats, so the reader must be symmetric: it must reject a record
# that decodes to a non-finite float instead of yielding ``inf``/``-inf`` to
# downstream consumers.
# ---------------------------------------------------------------------------


def test_iter_jsonl_rejects_overflowing_positive_number() -> None:
    with pytest.raises(ValueError):
        list(iter_jsonl(io.StringIO("1e400\n")))


def test_iter_jsonl_rejects_overflowing_negative_number() -> None:
    with pytest.raises(ValueError):
        list(iter_jsonl(io.StringIO("-1e400\n")))


def test_iter_jsonl_rejects_overflowing_number_nested_in_object() -> None:
    with pytest.raises(ValueError):
        list(iter_jsonl(io.StringIO('{"a": 1e400}\n')))


# ---------------------------------------------------------------------------
# partition_overlaps / assert_disjoint_partitions: string partitions are
# silently split into single characters.
#
# A partition value that is a plain ``str`` is treated as an iterable of
# characters (``set("item1") == {'i','t','e','m','1'}``), so two partitions
# such as "item1" and "item2" report a spurious character overlap and
# ``assert_disjoint_partitions`` raises a false "overlap detected". This is
# inconsistent with ``PartitionManifest`` in the same module, which rejects
# string identifiers explicitly. Expected behavior: reject string partitions
# with a clear ``ValueError`` instead of silently splitting into characters.
# ---------------------------------------------------------------------------


def test_partition_overlaps_rejects_string_partition() -> None:
    with pytest.raises(ValueError):
        partition_overlaps({"a": "item1", "b": "item2"})


def test_assert_disjoint_partitions_rejects_string_partition() -> None:
    # Two distinct single-string partitions must not be treated as sharing
    # characters (which produces a false "overlap detected" today). String
    # partitions should be rejected with a clear validation error that is
    # NOT an overlap report.
    with pytest.raises(ValueError) as exc_info:
        assert_disjoint_partitions({"a": "item1", "b": "item2"})
    assert "overlap" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# copy_and_hash: max_bytes raises (and copies nothing/partial) instead of
# truncating at the bound.
#
# ``copy_and_hash`` is documented as "optionally bounding output size", so a
# source larger than ``max_bytes`` should copy up to ``max_bytes`` bytes and
# return a result, not raise ``ValueError``. Today it rejects the whole first
# oversized chunk, raising after writing only the bytes of the partial chunks
# that happened to fit (e.g. 2 of 6 bytes), leaving an inconsistent partial
# output. Expected behavior: truncate cleanly at ``max_bytes`` and return
# ``bytes_written == max_bytes`` with the digest of exactly those bytes.
# ---------------------------------------------------------------------------


def test_copy_and_hash_truncates_at_max_bytes_bound() -> None:
    source = io.BytesIO(b"abcdef")
    destination = io.BytesIO()
    result = copy_and_hash(
        source,
        destination,
        max_bytes=3,
        chunk_size=2,
    )
    assert result.bytes_written == 3
    assert destination.getvalue() == b"abc"
    assert result.hexdigest == hashlib.sha256(b"abc").hexdigest()
