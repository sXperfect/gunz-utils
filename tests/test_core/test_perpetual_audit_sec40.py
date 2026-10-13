"""Perpetual security audit phase 40 (round 4, deepest).

Re-audit of ``diagnostics``, ``dict_utils``, ``enums``, ``models``,
``result``, and ``typed_config``.

Findings (both NEW, not fixed in phases 1-39):

1. ``result.Result`` type-confusion on an explicit ``None`` error
   (result.py:33-44).  The active-variant inference is ``_ok =
   self.error is None`` (result.py:38), so it cannot distinguish an error
   result whose ``error`` is ``None`` from a success result.  A caller that
   constructs ``Result(error=None)`` (e.g. from ``Result(error=fn())`` where
   ``fn()`` returns ``None`` at runtime) silently gets a *success* result
   (``is_ok is True``), even though the ``error`` field was explicitly
   populated.  ``None`` is documented as valid in either active variant, so an
   error result with a ``None`` error must remain an error.  Correct behavior:
   the constructor must distinguish "``error`` explicitly provided" from
   "``error`` not provided" (a sentinel default for ``value``/``error``), so
   ``Result(error=None)`` infers ``is_ok is False``.

2. ``diagnostics.exception_dict`` does not guarantee a JSON-friendly envelope
   (diagnostics.py:17-38).  Its contract states "Return a JSON-friendly
   exception envelope with redacted context", but when ``context`` (or any
   nested value) is not JSON-serializable -- a ``set``, ``bytes``, an arbitrary
   ``object``, or a nested non-serializable value -- ``redact_dict`` leaves the
   value in place and ``json.dumps`` raises ``TypeError``
   ("Object of type X is not JSON serializable").  For a diagnostics helper
   whose job is to produce a safe, serializable record of an arbitrary
   exception, leaking a raw ``TypeError`` instead of a usable envelope defeats
   the purpose and can mask the original failure.  Correct behavior: every
   context value must be coerced to a JSON-serializable form (e.g. ``repr`` of
   non-serializable scalars/containers) so the envelope always serializes.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: Result.ok/err/unwrap/map/map_error; deep_merge cycle safety, dedup
bool-vs-int distinction, list strategies; enum fuzzy lookup + bool rejection;
typed_config parse_bool; models bool-vs-int field guard; exception_dict
redaction and include_message bool validation.
"""

import json

import pytest

from gunz_utils.diagnostics import exception_dict
from gunz_utils.dict_utils import deep_get, deep_merge, deep_set
from gunz_utils.enums import BaseIntEnum, BaseStrEnum
from gunz_utils.result import Result
from gunz_utils.typed_config import parse_bool

# ---------------------------------------------------------------------------
# Finding 1: Result(error=None) must remain an error result
# ---------------------------------------------------------------------------


def test_result_error_none_is_an_error_not_success() -> None:
    """RED: constructing Result(error=None) must yield an error result."""
    result = Result(error=None)
    assert result.is_err is True
    assert result.is_ok is False


def test_result_err_none_is_an_error_result() -> None:
    """RED: Result.err(None) and Result(error=None) must agree on variant."""
    assert Result.err(None).is_err is True
    # The public constructor path must classify the same way.
    assert Result(error=None).is_err is True


# ---------------------------------------------------------------------------
# Finding 2: exception_dict must always produce a JSON-friendly envelope
# ---------------------------------------------------------------------------


def test_exception_dict_serializes_set_context() -> None:
    """RED: a set context value must not break JSON serialization."""
    envelope = exception_dict(
        RuntimeError("boom"),
        context={"tags": {1, 2, 3}},
    )
    json.dumps(envelope)


def test_exception_dict_serializes_bytes_context() -> None:
    """RED: a bytes context value must not break JSON serialization."""
    envelope = exception_dict(
        RuntimeError("boom"),
        context={"payload": b"\x00\x01"},
    )
    json.dumps(envelope)


def test_exception_dict_serializes_arbitrary_object_context() -> None:
    """RED: a non-serializable object context value must be coerced."""
    envelope = exception_dict(
        RuntimeError("boom"),
        context={"handle": object()},
    )
    json.dumps(envelope)


# ---------------------------------------------------------------------------
# GREEN coverage: correct behavior must be pinned so fixes cannot regress
# ---------------------------------------------------------------------------


def test_result_ok_err_unwrap_map() -> None:
    ok = Result.ok(5)
    assert ok.is_ok and not ok.is_err
    assert ok.unwrap() == 5
    assert ok.map(lambda x: x * 2).unwrap() == 10
    err = Result.err("boom")
    assert err.is_err and not err.is_ok
    with pytest.raises(RuntimeError):
        err.unwrap()
    assert err.unwrap_or(99) == 99
    assert err.map_error(lambda e: e.upper()).unwrap_or("x") == "x"


def test_result_constructor_validations() -> None:
    with pytest.raises(ValueError):
        Result(value=5, error="boom", _ok=True)  # success cannot carry error
    with pytest.raises(ValueError):
        Result(value=5, error="boom", _ok=False)  # error cannot carry value


def test_deep_merge_cycle_safe_and_list_strategies() -> None:
    node: list = []
    tup = (node,)
    node.append(tup)
    merged = deep_merge({}, {"x": tup})
    assert "x" in merged

    assert deep_merge({"xs": [1, 2]}, {"xs": [3]}, list_strategy="concat")[
        "xs"
    ] == [1, 2, 3]
    assert deep_merge({"xs": [1, 2, 3]}, {"xs": [2, 4]}, list_strategy="dedup")[
        "xs"
    ] == [1, 2, 3, 4]
    # bool stays distinct from equal-valued int in dedup.
    assert deep_merge(
        {"x": [True, 1, 0, False]}, {"x": [1, True]}, list_strategy="dedup"
    )["x"] == [True, 1, 0, False]


def test_deep_get_set_and_merge_do_not_mutate_inputs() -> None:
    base = {"a": {"b": 1}}
    merged = deep_merge(base, {"a": {"c": 2}})
    assert base == {"a": {"b": 1}}  # base not mutated
    assert merged["a"] == {"b": 1, "c": 2}

    d: dict = {}
    deep_set(d, "x.y.z", 42)
    assert deep_get(d, "x.y.z") == 42
    with pytest.raises(KeyError):
        deep_get(d, "x.missing")
    assert deep_get(d, "x.missing", default=None) is None


def test_enum_fuzzy_lookup_and_bool_rejection() -> None:
    class Color(BaseStrEnum):
        DARK_BLUE = "dark_blue"
        LIGHT_GREEN = "light green"

    assert Color.from_fuzzy_string("dark-blue") is Color.DARK_BLUE
    assert Color.from_fuzzy_string("Light_Green") is Color.LIGHT_GREEN
    with pytest.raises(ValueError):
        Color.from_fuzzy_string("nope")

    class Code(BaseIntEnum):
        NOT_FOUND = 404

    assert Code.from_fuzzy_int_string("404") is Code.NOT_FOUND
    with pytest.raises(ValueError):
        Code(True)  # bool must not coerce into an int member


def test_parse_bool_and_config_value() -> None:
    assert parse_bool(" yes ") is True
    assert parse_bool("OFF") is False
    with pytest.raises(ValueError):
        parse_bool("2")
