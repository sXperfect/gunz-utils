"""Optional Pydantic-backed runtime validation helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import functools
import typing as t

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from pydantic import ValidationError, validate_call

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"


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

        @functools.wraps(f)
        def wrapper(
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

                    #? Human-readable Pydantic messages can include arbitrary
                    #? custom-validator text. Expose only the stable error code
                    #? and input type so secret-bearing validator messages cannot
                    #? leak into the public TypeError.
                    input_type = type(input_val).__name__
                    errors.append(
                        f"Argument '{loc_str}': validation failed "
                        f"[{error_type}] (got type '{input_type}')"
                    )

                error_msg = (
                    f"Validation error in '{f.__name__}':\n"
                    + "\n".join(errors)
                )
                raise TypeError(error_msg) from None

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
