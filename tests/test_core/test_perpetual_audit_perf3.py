"""Perpetual correctness & performance audit regressions (phase 3).

Each test pins a defect found during the round-3 audit of
``gunz_utils.{binary,buffers,hashing,parsing,sampling}``. The tests currently
FAIL against the audited revision (f853635, which includes the phase-1 and
phase-2 fixes); they encode the expected post-fix behavior and should be
un-skipped once the implementation is corrected. Production code is
intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.hashing import short_hash
from gunz_utils.parsing import safe_float
from gunz_utils.sampling import sample_named_items


# ---------------------------------------------------------------------------
# short_hash: ``chars`` larger than the algorithm's digest length silently
# returns a shorter-than-requested prefix.
#
# ``short_hash`` validates ``chars`` against a fixed ``[4, 128]`` window, but
# the effective maximum is bounded by the digest length of the selected
# algorithm (md5 -> 32 hex chars, sha1 -> 40, sha256 -> 64, sha512/blake2b ->
# 128). For ``chars`` above that bound the function silently returns a shorter
# string, so callers cannot tell that their requested fingerprint length was
# not honored. Expected behavior: reject a ``chars`` value that exceeds the
# selected algorithm's hex-digest length with a clear ``ValueError`` instead of
# silently returning a truncated prefix.
# ---------------------------------------------------------------------------


def test_short_hash_rejects_chars_beyond_md5_digest_length() -> None:
    # md5 produces 32 hex characters; requesting 64 must not silently return 32.
    with pytest.raises(ValueError):
        short_hash(b"data", chars=64, algo="md5")


def test_short_hash_rejects_chars_beyond_sha1_digest_length() -> None:
    # sha1 produces 40 hex characters; requesting 64 must not silently return 40.
    with pytest.raises(ValueError):
        short_hash(b"data", chars=64, algo="sha1")


def test_short_hash_rejects_chars_beyond_sha256_digest_length() -> None:
    # sha256 produces 64 hex characters; requesting 128 must not silently
    # return 64.
    with pytest.raises(ValueError):
        short_hash(b"data", chars=128, algo="sha256")


# ---------------------------------------------------------------------------
# safe_float: raw boolean inputs are silently accepted as 1.0 / 0.0.
#
# ``safe_int`` explicitly rejects booleans (returns ``default``), and boolean
# parsing is the job of ``safe_bool``/``parse_bool``. ``safe_float``, however,
# does not reject booleans, so ``safe_float(True) == 1.0`` and
# ``safe_float(False) == 0.0``. A numeric config value that happens to arrive
# as a boolean is therefore silently coerced instead of being treated as
# invalid. Expected behavior: reject raw ``bool`` inputs (return ``default``),
# consistent with ``safe_int``.
# ---------------------------------------------------------------------------


def test_safe_float_rejects_true_bool() -> None:
    assert safe_float(True) is None
    assert safe_float(True, default=5.0) == 5.0


def test_safe_float_rejects_false_bool() -> None:
    assert safe_float(False) is None
    assert safe_float(False, default=5.0) == 5.0


# ---------------------------------------------------------------------------
# sample_named_items: ``limit`` is not validated as ``int | None``.
#
# A non-integer, non-``None`` ``limit`` (e.g. a float) passes the ``limit < 0``
# check and then fails later with a raw ``TypeError`` from the list slice
# (``eligible[:1.5]``), while a boolean ``limit`` is silently treated as 0/1.
# ``stable_priority`` validates its ``seed`` argument as an integer, so the
# companion API should validate ``limit`` the same way. Expected behavior:
# reject a ``limit`` that is not ``int | None`` (including ``bool``) with a
# clear ``ValueError``.
# ---------------------------------------------------------------------------


def test_sample_named_items_rejects_float_limit() -> None:
    with pytest.raises(ValueError):
        sample_named_items([("a", 1), ("b", 2)], limit=1.5)


def test_sample_named_items_rejects_bool_limit() -> None:
    with pytest.raises(ValueError):
        sample_named_items([("a", 1), ("b", 2)], limit=True)
