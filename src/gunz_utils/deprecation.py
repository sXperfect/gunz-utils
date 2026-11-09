"""Public API deprecation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import functools
import inspect
import warnings
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class GunzDeprecationWarning(DeprecationWarning):
    """Warning category for gunz-utils public API deprecations."""


def deprecated(
    message: str,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Mark a callable deprecated while preserving its signature metadata.

    Parameters
    ----------
    message : str
        message parameter.

    Returns
    -------
    Callable[[Callable[P, T]], Callable[P, T]]
        The result of the operation.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")

    def decorate(
        func: Callable[P, T],
    ) -> Callable[P, T]:
        """decorate() function.

        Parameters
        ----------
        func : Callable[P, T]
            func parameter.

        Returns
        -------
        Callable[P, T]
            The result of the operation.
        """
        if not callable(func):
            raise TypeError("func must be callable")

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapped(
                *args: P.args,
                **kwargs: P.kwargs,
            ) -> Any:
                warnings.warn(
                    message,
                    GunzDeprecationWarning,
                    stacklevel=2,
                )
                return await func(*args, **kwargs)

            async_wrapped.__deprecated__ = message  # type: ignore[attr-defined]
            return async_wrapped  # type: ignore[return-value]

        @functools.wraps(func)
        def wrapped(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> T:
            warnings.warn(
                message,
                GunzDeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        wrapped.__deprecated__ = message  # type: ignore[attr-defined]
        return wrapped

    return decorate


__all__ = ["GunzDeprecationWarning", "deprecated"]
