"""Perpetual correctness & performance audit regressions (phase 5).

Each test pins a defect found during the round-5 audit of
``gunz_utils.{identifiers,resources,result,enums,env}``. The tests currently
FAIL against the audited revision (b4b18c1, which includes the phase-1..4
fixes); they encode the expected post-fix behavior and should be un-skipped
once the implementation is corrected. Production code is intentionally left
untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import contextlib
import os

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.env import env, env_bool
from gunz_utils.enums import BaseIntEnum


@contextlib.contextmanager
def _set_env(key: str, value: str | None) -> None:
    """Temporarily set or unset an environment variable within the block."""
    previous = os.environ.get(key)
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


# ---------------------------------------------------------------------------
# BaseIntEnum: boolean inputs are silently accepted as integers, mapping
# True -> the value-1 member and False -> the value-0 member.
#
# ``BaseStrEnum.get_or_none(True)`` returns None (booleans are not valid
# strings), and the rest of the package rejects booleans explicitly (safe_int,
# safe_float, version validation, ...). ``BaseIntEnum``, however, inherits
# Python's ``int`` semantics, so ``Flag(True)`` / ``Flag.get_or_none(True)``
# return the member whose value is 1. This silently coerces a boolean into an
# integer member, inconsistent with ``BaseStrEnum`` and the package's strict
# bool handling. Expected: reject raw boolean inputs (return None).
# ---------------------------------------------------------------------------


class _Flag(BaseIntEnum):
    OFF = 0
    ON = 1


def test_base_int_enum_get_or_none_rejects_true_bool() -> None:
    assert _Flag.get_or_none(True) is None


def test_base_int_enum_get_or_none_rejects_false_bool() -> None:
    assert _Flag.get_or_none(False) is None


def test_base_int_enum_constructor_rejects_true_bool() -> None:
    with pytest.raises(ValueError):
        _Flag(True)


# ---------------------------------------------------------------------------
# env: an empty/whitespace-only variable value is treated as a present value
# instead of falling back to the caller's default.
#
# ``env("X", default=5)`` with ``X=""`` returns the empty string (or the raw
# whitespace) rather than the default ``5``, and ``env_bool("X", default=...)``
# with an empty value raises ``ValueError`` instead of returning the default.
# In a safe-defaults reader an unset or blank value should resolve to the
# default. Expected: treat an empty/whitespace-only value as unset and return
# the default.
# ---------------------------------------------------------------------------


def test_env_blank_value_returns_default() -> None:
    with _set_env("GUNZ_P5_BLANK", ""):
        assert env("GUNZ_P5_BLANK", default=5) == 5


def test_env_whitespace_value_returns_default() -> None:
    with _set_env("GUNZ_P5_BLANK", "   "):
        assert env("GUNZ_P5_BLANK", default=5) == 5


def test_env_bool_blank_value_returns_default() -> None:
    with _set_env("GUNZ_P5_BOOL_BLANK", ""):
        assert env_bool("GUNZ_P5_BOOL_BLANK", default=False) is False


# ---------------------------------------------------------------------------
# env: a float cast silently accepts non-finite results.
#
# ``env("X", cast=float)`` on an overflowing numeric literal such as ``"1e400"``
# returns ``inf`` (and ``"nan"`` is likewise accepted), with no finiteness
# guard. This is inconsistent with the package's ``safe_float`` parser, which
# rejects non-finite values by default (``allow_nan=False``), and it can let a
# non-finite value propagate into downstream numerical work. Expected: reject
# a non-finite float result (raise ``ValueError``), matching the package's
# finiteness conventions.
# ---------------------------------------------------------------------------


def test_env_float_rejects_overflowing_literal() -> None:
    with _set_env("GUNZ_P5_FLOAT", "1e400"):
        with pytest.raises(ValueError):
            env("GUNZ_P5_FLOAT", cast=float)
