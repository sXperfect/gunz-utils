"""Differential proof tests for optional runtime validation backends."""

from __future__ import annotations

import pytest

from gunz_utils.ext.validation_pydantic import type_checked as pydantic_type_checked
from gunz_utils.ext.validation_stdlib import type_checked as stdlib_type_checked


@pytest.mark.parametrize("decorator", [stdlib_type_checked, pydantic_type_checked])
def test_validation_backends_accept_matching_scalar_types(decorator) -> None:
    @decorator
    def identity(value: int) -> int:
        return value

    assert identity(7) == 7


def test_validation_backends_can_share_strict_int_contract() -> None:
    @stdlib_type_checked
    def stdlib_identity(value: int) -> int:
        return value

    @pydantic_type_checked(config={"strict": True})
    def pydantic_identity(value: int) -> int:
        return value

    for invalid in (True, "7"):
        with pytest.raises(TypeError):
            stdlib_identity(invalid)
        with pytest.raises(TypeError):
            pydantic_identity(invalid)


def test_pydantic_validation_error_redacts_input_value() -> None:
    @pydantic_type_checked(config={"strict": True})
    def accepts_int(secret: int) -> int:
        return secret

    sensitive = "do-not-leak-this-value"
    with pytest.raises(TypeError) as captured:
        accepts_int(sensitive)
    message = str(captured.value)
    assert sensitive not in message
    assert "str" in message
