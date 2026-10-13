"""Phase 40 perpetual audit: round-4 (deepest) re-audit of six core modules.

diagnostics.py, dict_utils.py, enums.py, models.py, result.py, typed_config.py.

Verified correct at base 7d38a92 (GREEN companion tests below):
- diagnostics: exception_dict envelope + redaction.
- dict_utils: deep_get/deep_set dotted paths, deep_merge replace/concat,
  hashable dedup, non-mutation of inputs, cycle-safe isolation.
- enums: BaseStrEnum fuzzy lookup, alias resolution, input-length guard,
  OptionalBaseStrEnum NONE member, BaseIntEnum bool rejection.
- models: GunzBaseModel bool-for-int rejection (pydantic v2).
- result: Result ok/err inference, unwrap/map/map_error.
- typed_config: ConfigValue, parse_bool, convert.

One NEW correctness finding:

1) dict_utils.deep_merge list_strategy="dedup" (_merge_lists,
   src/gunz_utils/dict_utils.py:422-436) is non-symmetric / order-dependent
   when the two lists contain values that are equal but differ in hashability.
   ``{1, 2} == frozenset({1, 2})`` but a set is unhashable and a frozenset is
   hashable. ``deep_merge({"xs": [s]}, {"xs": [fs]}, "dedup")`` returns
   ``[s, fs]`` (both kept, 2 items) while ``deep_merge({"xs": [fs]},
   {"xs": [s]}, "dedup")`` returns ``[fs]`` (1 item). The dedup tracks
   hashable items in ``seen_hashable`` and unhashable items separately in
   ``seen_unhashable``; the ``dedup_key in seen_hashable`` membership test
   falls back to linear ``==`` when the needle is unhashable, so an unhashable
   item that equals an already-seen hashable item is silently dropped in one
   ordering but the reverse ordering keeps both. For equal values a dedup must
   remove the duplicate regardless of which side (base/override) supplied it;
   the result length must not depend on input ordering (RED).

This test is expected to be RED against base 7d38a92 for the finding and GREEN
for the companion behaviors.
"""

from __future__ import annotations

import pytest

from gunz_utils.diagnostics import exception_dict
from gunz_utils.dict_utils import deep_get, deep_merge, deep_set
from gunz_utils.enums import BaseIntEnum, BaseStrEnum, OptionalBaseStrEnum
from gunz_utils.result import Result
from gunz_utils.typed_config import ConfigValue, convert, parse_bool

# ---------------------------------------------------------------------------
# 1) dict_utils.deep_merge dedup is order-dependent / non-symmetric (RED)
# ---------------------------------------------------------------------------


def test_deep_merge_dedup_equal_cross_hashability_is_symmetric():
    s: set = {1, 2}
    fs = frozenset({1, 2})
    assert s == fs  # precondition: equal values, different hashability
    left = deep_merge({"xs": [s]}, {"xs": [fs]}, list_strategy="dedup")["xs"]
    right = deep_merge({"xs": [fs]}, {"xs": [s]}, list_strategy="dedup")["xs"]
    # Dedup must remove the duplicate in both orderings: same length.
    assert len(left) == len(right) == 1


def test_deep_merge_dedup_equal_hashable_is_symmetric():
    # Control: fully-hashable equal items already dedup symmetrically.
    left = deep_merge({"xs": [1]}, {"xs": [1]}, list_strategy="dedup")["xs"]
    right = deep_merge({"xs": [1]}, {"xs": [1]}, list_strategy="dedup")["xs"]
    assert left == [1]
    assert right == [1]


# ---------------------------------------------------------------------------
# GREEN companions — dict_utils
# ---------------------------------------------------------------------------


def test_deep_get_and_deep_set():
    d = {"a": {"b": 1}}
    assert deep_get(d, "a.b") == 1
    assert deep_get(d, "a.c", default=None) is None
    with pytest.raises(KeyError):
        deep_get(d, "a.missing")
    deep_set(d, "a.c", 2)
    assert d == {"a": {"b": 1, "c": 2}}


def test_deep_merge_replace_and_concat_and_hashable_dedup():
    assert deep_merge({"a": {"b": 1}}, {"a": {"c": 2}}) == {"a": {"b": 1, "c": 2}}
    assert deep_merge({"xs": [1, 2]}, {"xs": [3]}, list_strategy="replace")["xs"] == [3]
    assert deep_merge(
        {"xs": [1, 2]}, {"xs": [3]}, list_strategy="concat"
    )["xs"] == [1, 2, 3]
    assert deep_merge(
        {"xs": [1, 2, 1]}, {"xs": [2, 3]}, list_strategy="dedup"
    )["xs"] == [1, 2, 3]
    assert deep_merge(
        {"xs": [1]}, {"xs": [True]}, list_strategy="dedup"
    )["xs"] == [1, True]


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"b": 1}, "xs": [1, 2]}
    override = {"a": {"c": 2}, "xs": [3]}
    deep_merge(base, override)
    assert base == {"a": {"b": 1}, "xs": [1, 2]}
    assert override == {"a": {"c": 2}, "xs": [3]}


# ---------------------------------------------------------------------------
# GREEN companions — result
# ---------------------------------------------------------------------------


def test_result_variants_and_transforms():
    ok = Result.ok(5)
    err = Result.err(ValueError("boom"))
    assert ok.is_ok and not ok.is_err and ok.unwrap() == 5
    assert err.is_err
    with pytest.raises(RuntimeError):
        err.unwrap()
    assert err.unwrap_or(0) == 0
    assert ok.map(lambda x: x + 1).unwrap() == 6
    assert ok.map_error(lambda e: e).is_ok
    assert err.map(lambda x: x).is_err


def test_result_constructor_guards():
    with pytest.raises(ValueError):
        Result(value=1, error=2)
    assert Result.ok(None).is_ok
    assert Result.err(None).is_err


# ---------------------------------------------------------------------------
# GREEN companions — typed_config
# ---------------------------------------------------------------------------


def test_parse_bool():
    assert parse_bool("true") is True
    assert parse_bool("  YES ") is True
    assert parse_bool("0") is False
    assert parse_bool("off") is False
    with pytest.raises(ValueError):
        parse_bool("maybe")
    with pytest.raises(TypeError):
        parse_bool(1)  # type: ignore[arg-type]


def test_config_value_convert():
    cv = convert("42", int, source="env")
    assert isinstance(cv, ConfigValue)
    assert cv.value == 42
    assert cv.source == "env"


# ---------------------------------------------------------------------------
# GREEN companions — enums
# ---------------------------------------------------------------------------


class _Color(BaseStrEnum):
    DARK_BLUE = "dark_blue"
    LIGHT_GREEN = "light green"


class _Code(BaseIntEnum):
    NOT_FOUND = 404
    OK = 200


class _Opt(OptionalBaseStrEnum):
    NONE = "none"
    SOME = "some"


def test_str_enum_fuzzy_and_limit():
    assert _Color.from_fuzzy_string("DARK_BLUE") is _Color.DARK_BLUE
    assert _Color.from_fuzzy_string("dark-blue") is _Color.DARK_BLUE
    assert _Color.from_fuzzy_string("LIGHT GREEN") is _Color.LIGHT_GREEN
    with pytest.raises(ValueError):
        _Color.from_fuzzy_string("z" * 2000)
    assert _Color.get_or_none("nope") is None


def test_optional_enum_none():
    assert _Opt(None) is _Opt.NONE
    assert _Opt.get_or_none("SOME") is _Opt.SOME


def test_int_enum_bool_rejected():
    with pytest.raises(ValueError):
        _Code(True)
    assert _Code.from_fuzzy_int_string("404") is _Code.NOT_FOUND
    assert _Code.get_or_none("ok") is _Code.OK


# ---------------------------------------------------------------------------
# GREEN companions — models (pydantic) + diagnostics
# ---------------------------------------------------------------------------


def test_gunz_base_model_bool_int_rejection():
    from pydantic import ValidationError

    from gunz_utils.models import GunzBaseModel

    class M(GunzBaseModel):
        count: int

    assert M(count=5).count == 5
    with pytest.raises(ValidationError):
        M(count=True)


def test_exception_dict():
    exc = ValueError("secret value")
    d = exception_dict(
        exc,
        context={"user": "alice", "password": "hunter2"},
        include_message=False,
    )
    assert d["type"] == "ValueError"
    assert "message" not in d
    assert d["context"]["user"] == "alice"
    assert d["context"]["password"] != "hunter2"  # secret-named key redacted
    dm = exception_dict(exc, include_message=True)
    assert dm["message"] == "secret value"
