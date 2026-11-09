"""Tests for coercing a config spec from an object, mapping, or fields."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import UNSET
from gunz_utils.spec import coerce_spec_sequence, from_object_or_fields


@dataclass(frozen=True)
class DemoSpec:
    size: int = 40
    label: str | None = None
    flag: bool = False


def test_returns_instance_unchanged() -> None:
    spec = DemoSpec(size=8)
    assert from_object_or_fields(DemoSpec, spec, {"size": UNSET, "label": UNSET}) is spec


def test_builds_from_mapping() -> None:
    spec = from_object_or_fields(DemoSpec, {"size": 16, "label": "a"}, {})
    assert spec == DemoSpec(size=16, label="a")


def test_builds_from_fields_ignoring_unset() -> None:
    spec = from_object_or_fields(DemoSpec, None, {"size": 8, "label": UNSET, "flag": UNSET})
    assert spec == DemoSpec(size=8)


def test_keeps_real_none_field() -> None:
    spec = from_object_or_fields(DemoSpec, None, {"size": 8, "label": None})
    assert spec == DemoSpec(size=8, label=None)


def test_default_instance_when_nothing_supplied() -> None:
    spec = from_object_or_fields(DemoSpec, None, {"size": UNSET, "label": UNSET})
    assert spec == DemoSpec()


def test_none_when_allow_none_and_nothing_supplied() -> None:
    result = from_object_or_fields(
        DemoSpec, None, {"size": UNSET, "label": UNSET}, allow_none=True
    )
    assert result is None


def test_rejects_object_and_fields_together() -> None:
    with pytest.raises(ValueError, match="not both"):
        from_object_or_fields(DemoSpec, DemoSpec(), {"size": 8})


def test_rejects_unsupported_value_type() -> None:
    with pytest.raises(ValueError, match="instance"):
        from_object_or_fields(DemoSpec, 42, {})


def test_coerces_mixed_sequence() -> None:
    items = [
        DemoSpec(size=8),
        {"size": 16, "label": "a"},
    ]
    result = coerce_spec_sequence(DemoSpec, items)
    assert result == (DemoSpec(size=8), DemoSpec(size=16, label="a"))
    assert isinstance(result[0], DemoSpec)
    assert isinstance(result[1], DemoSpec)


def test_coerces_empty_sequence() -> None:
    assert coerce_spec_sequence(DemoSpec, []) == ()


def test_coerce_sequence_rejects_unsupported_item() -> None:
    with pytest.raises(ValueError, match="instances or field mappings"):
        coerce_spec_sequence(DemoSpec, [DemoSpec(), 42])
