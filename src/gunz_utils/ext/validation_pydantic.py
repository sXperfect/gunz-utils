"""Optional Pydantic-backed runtime validation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import functools
import typing as t

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from pydantic import ValidationError, validate_call

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"


def _validation_error_message(
    exc: ValidationError,
    func_name: str,
) -> str:
    """Build a redacted validation error message.

    Pydantic messages can include arbitrary custom-validator text; expose only
    the stable error code and input type so secret-bearing validator messages
    and original input values cannot leak into the public TypeError.
    """
    errors: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        input_val = error.get("input", "unknown")
        error_type = str(error.get("type", "validation_error"))

        clean_loc = [
            str(item)
            for item in loc
            if item not in ("args", "kwargs")
        ]
        loc_str = " -> ".join(clean_loc) if clean_loc else "input"
        input_type = type(input_val).__name__
        errors.append(
            f"Argument '{loc_str}': validation failed "
            f"[{error_type}] (got type '{input_type}')"
        )

    return (
        f"Validation error in '{func_name}':\n"
        + "\n".join(errors)
    )


def type_checked(
    func: t.Callable | None = None,
    **kwargs: t.Any,
) -> t.Callable:
    """Wrap pydantic.validate_call with value-redacted public errors.

    Parameters
    ----------
    func : t.Callable | None
        func parameter.
    kwargs : t.Any
        kwargs parameter.

    Returns
    -------
    t.Callable
        The result of the operation.
    """

    def decorator(
        f: t.Callable,
    ) -> t.Callable:
        """decorator() function.

        Parameters
        ----------
        f : t.Callable
            f parameter.

        Returns
        -------
        t.Callable
            The result of the operation.
        """
        #? Default to strict validation so this backend matches the stdlib
        #? analog's bool-vs-int / numeric separation (e.g. a bool or string is
        #? not silently coerced into an int). Callers may override by passing
        #? an explicit ``config``.
        options = dict(kwargs)
        config = dict(options.get("config") or {})
        config.setdefault("strict", True)
        options["config"] = config
        validated_func = validate_call(f, **options)

        if asyncio.iscoroutinefunction(f):
            #? pydantic.validate_call on an async function defers validation to
            #? await time: calling it returns a coroutine without raising, so a
            #? synchronous try/except would let the raw ValidationError (with
            #? the original input value) escape. Await inside the guarded try so
            #? async calls surface the same redacted TypeError as sync calls.
            @functools.wraps(f)
            async def wrapper(
                *args: t.Any,
                **kw: t.Any,
            ) -> t.Any:
                """wrapper() function.

                Parameters
                ----------
                args : t.Any
                    args parameter.
                kw : t.Any
                    kw parameter.

                Returns
                -------
                t.Any
                    The result of the operation.
                """
                try:
                    return await validated_func(*args, **kw)
                except ValidationError as exc:
                    raise TypeError(
                        _validation_error_message(exc, f.__name__)
                    ) from None

            return wrapper

        @functools.wraps(f)
        def wrapper_sync(
            *args: t.Any,
            **kw: t.Any,
        ) -> t.Any:
            """wrapper() function.

            Parameters
            ----------
            args : t.Any
                args parameter.
            kw : t.Any
                kw parameter.

            Returns
            -------
            t.Any
                The result of the operation.
            """
            try:
                return validated_func(*args, **kw)
            except ValidationError as exc:
                raise TypeError(
                    _validation_error_message(exc, f.__name__)
                ) from None

        return wrapper_sync

    if func is not None:
        return decorator(func)
    return decorator
