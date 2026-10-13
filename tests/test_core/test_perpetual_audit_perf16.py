"""Phase 16 perpetual audit: round-3 re-audit of enums/resilience/models/pipeline.

Focused on the deepest corners a prior pass could miss: an enum member NAME
that collides exactly with another member's VALUE, and a Pydantic
``Literal[int]`` field that silently coerces a ``bool``.

These tests are expected to be RED against base ``a898068`` and document the
correct behavior after a fix.
"""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from gunz_utils.enums import BaseStrEnum
from gunz_utils.models import GunzBaseModel


# ---------------------------------------------------------------------------
# enums.BaseStrEnum.from_fuzzy_string: a member NAME that equals another
# member's VALUE resolves to the name-owner, not the value-owner.
#
# Phase 14 fixed the case where a member's *lowercased name* shadowed another
# member's value (FOO="bar"/BAR="foo"). But the phase-14 fix added an exact,
# case-sensitive *name* check (step 2) that runs BEFORE the value lookup. When
# one member's name exactly equals another member's value, that name check
# overrides value-owner resolution and returns the WRONG member.
#
# Example: class E(BaseStrEnum): A = "a"; B = "A". The value "A" belongs to B
# (E("A") is E.B), but from_fuzzy_string("A") returns E.A because "A" is also
# A's name. Expected: resolving a member's own value returns that member.
# ---------------------------------------------------------------------------
def test_from_fuzzy_string_name_collides_with_value_resolves_value_owner() -> None:
    class E(BaseStrEnum):
        A = "a"
        B = "A"  # B's VALUE "A" equals A's NAME "A"

    # Direct value lookup agrees the owner of value "A" is B.
    assert E("A") is E.B

    # Resolving B's own value must return B, not A.
    assert E.from_fuzzy_string(E.B.value) is E.B, (
        'from_fuzzy_string(B.value="A") should return B (the owner of value '
        '"A"), not A (shadowed by A\'s exact name)'
    )

    # A's own value is unaffected.
    assert E.from_fuzzy_string(E.A.value) is E.A


def test_get_or_none_value_round_trip_with_name_value_collision() -> None:
    class E(BaseStrEnum):
        A = "a"
        B = "A"

    # Round-tripping a member's value through get_or_none must return the owner.
    assert E.get_or_none(E.B.value) is E.B
    assert E.get_or_none(E.A.value) is E.A


# ---------------------------------------------------------------------------
# models.GunzBaseModel: the bool-vs-int rejection misses Literal[int] fields.
#
# _annotation_is_int (models.py) only recognises bare ``int`` and ``Union`` /
# ``X | None`` annotations. A field annotated ``Literal[1, 2]`` is int-typed
# but ``_annotation_is_int`` returns False, so the ``_reject_bool_for_int_fields``
# guard never fires and Pydantic lax mode silently coerces True -> 1 into the
# int-typed Literal field, contradicting the documented bool-vs-int separation.
# ---------------------------------------------------------------------------
def test_model_rejects_bool_for_literal_int_field() -> None:
    class M(GunzBaseModel):
        level: Literal[1, 2]

    with pytest.raises(ValidationError):
        M(level=True)

    # Control: a genuine int literal value is still accepted.
    assert M(level=1).level == 1
