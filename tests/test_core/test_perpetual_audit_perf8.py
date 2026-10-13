"""Perpetual correctness & performance audit regressions (phase 8).

Each test pins a defect found during the round-8 audit of
``gunz_utils.{models,pipeline}`` and the optional validation ext modules.
The tests currently FAIL against the audited revision (ab2f68a, which
includes the phase-1..7 fixes); they encode the expected post-fix behavior
and should pass once the implementation is corrected. Production code is
intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import typing as t

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest
from pydantic import ValidationError

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.ext.validation_pydantic import type_checked as type_checked_pyd
from gunz_utils.ext.validation_stdlib import type_checked as type_checked_stdlib
from gunz_utils.models import GunzBaseModel

# ---------------------------------------------------------------------------
# ext.validation_stdlib.type_checked: ``tuple[()]`` (the empty-tuple type) is
# mis-validated and accepts any single-element tuple.
#
# ``_check_one`` handles a subscripted tuple as either ``(T, ...)`` (all
# elements of T) or a fixed-length tuple. ``tuple[()]`` is neither: its args
# are ``((),)``, which falls into the fixed-length branch where
# ``len(value) == len(args)`` accepts any 1-tuple and ``_check_one(item, ())``
# passes because ``()`` is not a type (pass-through). The empty-tuple type
# ``tuple[()]`` should only accept ``()``. Expected: reject any non-empty
# tuple for an annotation of ``tuple[()]``.
# ---------------------------------------------------------------------------


@type_checked_stdlib
def _stdlib_takes_empty_tuple(x: tuple[()]) -> tuple[()]:
    return x


def test_stdlib_tuple_empty_rejects_nonempty_tuple() -> None:
    with pytest.raises(TypeError):
        _stdlib_takes_empty_tuple((1,))


def test_stdlib_tuple_empty_accepts_empty_tuple() -> None:
    assert _stdlib_takes_empty_tuple(()) == ()


# ---------------------------------------------------------------------------
# ext.validation_pydantic.type_checked: lax coercion silently accepts bool and
# string values for an ``int`` parameter, diverging from the documented
# stdlib analog.
#
# The stdlib backend explicitly rejects a ``bool`` for an ``int`` annotation
# (validation_stdlib.py) and rejects a non-numeric ``str`` for ``int``. The
# pydantic backend wraps ``pydantic.validate_call`` with default (lax) config,
# so ``f(True)`` -> 1 and ``f("5")`` -> 5 are silently coerced. The two
# backends are documented as analogs but disagree on bool-vs-int / numeric
# coercion. Expected: reject ``bool`` (and non-int) inputs for an ``int``
# parameter, matching the stdlib backend's strict bool-vs-int separation.
# ---------------------------------------------------------------------------


@type_checked_pyd
def _pyd_takes_int(x: int) -> int:
    return x


def test_pydantic_type_checked_rejects_bool_for_int() -> None:
    with pytest.raises(TypeError):
        _pyd_takes_int(True)


def test_pydantic_type_checked_rejects_str_for_int() -> None:
    with pytest.raises(TypeError):
        _pyd_takes_int("5")


# ---------------------------------------------------------------------------
# models.GunzBaseModel: a bool is silently coerced into an ``int`` field even
# though the base model is documented as providing "strict config defaults".
#
# ``GunzBaseModel`` sets ``extra="forbid"``, ``str_strip_whitespace=True`` and
# ``validate_assignment=True`` but does not enable pydantic strict mode, so
# ``MyRecord(n=True)`` -> ``n == 1`` and ``MyRecord(n="5")`` -> ``n == 5``
# (and a ``bool`` field accepts ``1`` -> ``True``). This is the bool-vs-int
# separation the package enforces elsewhere (e.g. the stdlib ``type_checked``
# rejects ``bool`` for ``int``) and contradicts the "strict config defaults"
# promise. Expected: reject a ``bool``/non-``int`` value for an ``int`` field.
# ---------------------------------------------------------------------------


class _StrictIntModel(GunzBaseModel):
    n: int
    flag: bool


def test_models_rejects_bool_for_int_field() -> None:
    with pytest.raises(ValidationError):
        _StrictIntModel(n=True, flag=True)


@type_checked_stdlib
def _stdlib_takes_bare_tuple(x: t.Tuple) -> t.Tuple:  # noqa: UP006
    return x


def test_stdlib_bare_tuple_accepts_non_empty() -> None:
    assert _stdlib_takes_bare_tuple((1, 2)) == (1, 2)


class _OptionalIntModel(GunzBaseModel):
    n: int | None


def test_models_rejects_bool_for_optional_int_field() -> None:
    with pytest.raises(ValidationError):
        _OptionalIntModel(n=True)
