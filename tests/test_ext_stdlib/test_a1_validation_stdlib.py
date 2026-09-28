"""Proof tests for the stdlib runtime-validation backend."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

import pytest

from gunz_utils.ext.validation_stdlib import type_checked


def test_pep604_union_is_enforced_recursively() -> None:
    @type_checked
    def accepts(value: int | None) -> int | None:
        return value

    assert accepts(3) == 3
    assert accepts(None) is None

    with pytest.raises(TypeError):
        accepts("3")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        accepts(True)


def test_nested_container_generics_validate_elements() -> None:
    @type_checked
    def accepts(
        value: list[dict[str, tuple[int, ...]]],
    ) -> int:
        return len(value)

    assert accepts([{"x": (1, 2)}, {"y": ()}]) == 2

    with pytest.raises(TypeError):
        accepts([{"x": (1, "bad")}])  # type: ignore[list-item]

    with pytest.raises(TypeError):
        accepts([{"x": [1, 2]}])  # type: ignore[dict-item]


def test_fixed_tuple_shape_is_enforced() -> None:
    @type_checked
    def accepts(value: tuple[int, str]) -> tuple[int, str]:
        return value

    assert accepts((1, "x")) == (1, "x")

    with pytest.raises(TypeError):
        accepts((1, 2))  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        accepts((1, "x", "extra"))  # type: ignore[arg-type]


def test_literal_comparison_is_type_strict() -> None:
    @type_checked
    def accepts(value: Literal[1, "one"]) -> object:
        return value

    assert accepts(1) == 1
    assert accepts("one") == "one"

    with pytest.raises(TypeError):
        accepts(True)  # type: ignore[arg-type]


def test_annotated_validates_underlying_type() -> None:
    @type_checked
    def accepts(value: Annotated[int, "metadata"]) -> int:
        return value

    assert accepts(4) == 4
    with pytest.raises(TypeError):
        accepts("4")  # type: ignore[arg-type]


def test_callable_outer_type_is_validated() -> None:
    @type_checked
    def accepts(callback: Callable[[], None]) -> object:
        return callback

    def function() -> None:
        return None

    assert accepts(function) is function

    with pytest.raises(TypeError):
        accepts(3)  # type: ignore[arg-type]


def test_backend_specific_decorator_options_are_rejected() -> None:
    with pytest.raises(TypeError, match="validator options"):

        @type_checked(config={"strict": True})
        def configured(value: int) -> int:
            return value


def test_sensitive_nested_values_are_not_rendered_in_error() -> None:
    sensitive = "nested-secret-value"

    @type_checked
    def accepts(value: dict[str, list[int]]) -> int:
        return len(value)

    with pytest.raises(TypeError) as captured:
        accepts({"secret": [sensitive]})  # type: ignore[list-item]

    message = str(captured.value)
    assert sensitive not in message
    assert "dict" in message
