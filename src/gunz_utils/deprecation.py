"""Public API deprecation helpers."""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class GunzDeprecationWarning(DeprecationWarning):
    """Warning category for gunz-utils public API deprecations."""


def deprecated(
    message: str,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Mark a callable deprecated while preserving its signature metadata."""
    def decorate(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            warnings.warn(
                message,
                GunzDeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapped

    return decorate


__all__ = ["GunzDeprecationWarning", "deprecated"]
