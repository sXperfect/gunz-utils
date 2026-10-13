"""Public API deprecation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import functools
import inspect
import warnings
from collections.abc import AsyncIterator, Callable
from typing import ParamSpec, TypeVar

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
        if asyncio.iscoroutinefunction(func):
            #? Keep deprecated async functions recognizable as coroutine
            #? functions (asyncio.iscoroutinefunction/inspect.iscoroutinefunction
            #? must stay True) so async consumers that dispatch on
            #? coroutine-function-ness are not mis-handled.
            @functools.wraps(func)
            async def wrapped(
                *args: P.args,
                **kwargs: P.kwargs,
            ) -> T:
                """wrapped() function.

                Parameters
                ----------
                args : P.args
                    args parameter.
                kwargs : P.kwargs
                    kwargs parameter.

                Returns
                -------
                T
                    The result of the operation.
                """
                warnings.warn(
                    message,
                    GunzDeprecationWarning,
                    stacklevel=2,
                )
                return await func(*args, **kwargs)

            return wrapped

        if inspect.isasyncgenfunction(func):
            #? An async generator function is not a coroutine function, so the
            #? coroutine branch above does not catch it. Keep deprecated async
            #? generator functions recognizable as such
            #? (inspect.isasyncgenfunction must stay True) so consumers that
            #? dispatch on async-generator-function-ness are not mis-handled.
            @functools.wraps(func)
            async def wrapped(
                *args: P.args,
                **kwargs: P.kwargs,
            ) -> AsyncIterator[T]:
                """wrapped() function.

                Parameters
                ----------
                args : P.args
                    args parameter.
                kwargs : P.kwargs
                    kwargs parameter.

                Yields
                ------
                T
                    items from the deprecated async generator.
                """
                warnings.warn(
                    message,
                    GunzDeprecationWarning,
                    stacklevel=2,
                )
                async for item in func(*args, **kwargs):
                    yield item

            return wrapped

        @functools.wraps(func)
        def wrapped(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> T:
            """wrapped() function.

            Parameters
            ----------
            args : P.args
                args parameter.
            kwargs : P.kwargs
                kwargs parameter.

            Returns
            -------
            T
                The result of the operation.
            """
            warnings.warn(
                message,
                GunzDeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapped

    return decorate


__all__ = ["GunzDeprecationWarning", "deprecated"]
