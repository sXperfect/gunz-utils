"""Perpetual correctness & performance audit regressions (phase 10).

Each test pins a defect found during the round-2 re-audit of
``dict_utils``, ``sampling``, and ``streaming`` (and related modules).
The tests currently FAIL against the audited revision (24fdab6, which
includes the phase-1..9 fixes); they encode the expected post-fix behavior
and should pass once the implementation is corrected. Production code is
intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import io

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.dict_utils import deep_get, deep_set
from gunz_utils.sampling import sample_named_items
from gunz_utils.streaming import copy_and_hash

# ---------------------------------------------------------------------------
# dict_utils.deep_get: a non-string path segment crashes with an internal
# ``TypeError`` from ``str.join``, even though ``deep_set`` accepts and
# creates exactly such keys (an int-keyed nested mapping). This asymmetry
# means a value written by ``deep_set`` at an integer-keyed path cannot be
# read back by ``deep_get``.
#
# ``_normalize_path`` (dict_utils.py) accepts any non-empty segment -- it
# only rejects empty strings -- so ``deep_set(d, ["a", 1], v)`` builds
# ``{"a": {1: v}}`` without complaint. But ``deep_get`` computes
# ``dotted = separator.join(parts)`` (dict_utils.py) before traversing, and
# ``str.join`` raises ``TypeError: sequence item 1: expected str instance``
# for the integer segment. The error is raised even when a ``default`` is
# supplied, because the join happens unconditionally up front. Expected:
# ``deep_get`` traverses the same integer-keyed path ``deep_set`` can write,
# returning the stored value (and honoring ``default`` on a miss).
# ---------------------------------------------------------------------------


def test_deep_get_reads_back_int_keyed_path_set_by_deep_set() -> None:
    d: dict = {}
    deep_set(d, ["a", 1], "x")
    assert d == {"a": {1: "x"}}
    assert deep_get(d, ["a", 1]) == "x"


def test_deep_get_with_non_string_segment_honors_default() -> None:
    assert deep_get({"a": {1: "x"}}, ["a", 2], default="D") == "D"


# ---------------------------------------------------------------------------
# sampling.sample_named_items: a single string passed as ``include_patterns``
# (or ``exclude_patterns``) is silently iterated as a sequence of characters
# instead of being treated as one glob pattern, producing wrong filtering with
# no error.
#
# The loop ``any(fnmatch.fnmatchcase(name, pattern) for pattern in
# include_patterns)`` (sampling.py) iterates whatever is passed. A bare string
# like ``"ab"`` is therefore split into the two one-character patterns ``"a"``
# and ``"b"``. For the items ``[("a", 1), ("ab", 2), ("b", 3)]`` with
# ``include_patterns="ab"`` the current code keeps ``"a"`` and ``"b"`` (each
# matches one character pattern) and drops ``"ab"`` -- the exact opposite of
# the intended single-pattern semantics, which keep only ``"ab"``. Expected:
# a bare string is treated as a single glob pattern (or rejected loudly), not
# silently split into characters.
# ---------------------------------------------------------------------------


def test_sample_named_items_string_pattern_not_split_into_characters() -> None:
    items = [("a", 1), ("ab", 2), ("b", 3)]
    assert sample_named_items(items, limit=None, include_patterns="ab") == [
        ("ab", 2)
    ]


# ---------------------------------------------------------------------------
# streaming.copy_and_hash: reads the ENTIRE source even after ``max_bytes``
# has been written, so it does not actually bound reads on an oversized
# source.
#
# ``copy_and_hash`` loops ``while chunk := source.read(chunk_size):
# writer.write(chunk)`` (streaming.py); ``DigestWriter.write`` truncates and
# returns ``0`` once the limit is reached, but the loop keeps pulling chunks
# from the source to EOF. For a source of 1000 bytes with ``max_bytes=100``
# the helper reads all 1000 bytes while writing only 100. On a genuinely
# oversized source this defeats the purpose of a "bounded copy-and-hash":
# it reads the whole thing instead of stopping at the bound. Expected: the
# copy stops reading from the source once ``max_bytes`` bytes have been
# written, so bytes read from the source are bounded by the limit (rounded up
# to the chunk size) rather than the full source length.
# ---------------------------------------------------------------------------


class _CountingReader(io.BytesIO):
    def __init__(self, data: bytes, chunk: int) -> None:
        super().__init__(data)
        self._chunk = chunk
        self.total_read = 0

    def read(self, size: int = -1) -> bytes:  # noqa: A003 - mirrors io API
        out = super().read(self._chunk)
        self.total_read += len(out)
        return out


def test_copy_and_hash_stops_reading_once_max_bytes_written() -> None:
    source = _CountingReader(b"x" * 1000, 256)
    destination = io.BytesIO()
    result = copy_and_hash(source, destination, max_bytes=100)
    assert result.bytes_written == 100
    assert source.total_read <= 512
