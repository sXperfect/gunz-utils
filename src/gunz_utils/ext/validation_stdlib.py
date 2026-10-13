"""Stdlib-only analog of `gunz_utils.ext.validation_pydantic.type_checked`.

No pydantic import. Validates parameter annotations against actual call
args at runtime using `inspect.signature` + `isinstance` + `typing.get_origin`.
Raises `TypeError` on type mismatch with a value-redacted message.

Coverage:
  - Bare classes (int, str, list, dict, tuple, set, bool, etc.)
  - `Optional[X]` / `X | None` / `Union[X, ...]`
  - `Literal` and the underlying type of `Annotated`
  - `*args: T` → each element validated against T
  - `**kw: T`  → each value validated against T
  - Recursive list/dict/tuple/set/frozenset generics
  - Callable outer-type validation

Unsupported constructs are treated as pass-through rather than guessed.
Backend-specific decorator options are rejected explicitly.
"""
# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
import asyncio
import functools
import inspect
import types
import typing as t
from collections import abc as cabc

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .._version import __version__ as __version__

__all__ = ["type_checked"]


def _check_one(
    value: t.Any,
    annotation: t.Any,
) -> bool:
    """Recursively validate the runtime subset promised by this backend.

    Parameters
    ----------
    value : t.Any
        value parameter.
    annotation : t.Any
        annotation parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
    if annotation is t.Any:
        return True
    if annotation is None or annotation is type(None):
        return value is None

    origin = t.get_origin(annotation)
    args = t.get_args(annotation)

    if origin is None:
        if not isinstance(annotation, type):
            return True
        if annotation is int and isinstance(value, bool):
            return False
        return isinstance(value, annotation)

    if origin is t.Annotated:
        return _check_one(value, args[0])

    if origin in (t.Union, types.UnionType):
        return any(_check_one(value, arg) for arg in args)

    if origin is t.Literal:
        return any(
            type(value) is type(candidate) and value == candidate
            for candidate in args
        )

    if origin is list:
        return isinstance(value, list) and (
            not args or all(_check_one(item, args[0]) for item in value)
        )

    if origin is dict:
        if not isinstance(value, dict):
            return False
        if len(args) != 2:
            return True
        key_type, value_type = args
        return all(
            _check_one(key, key_type) and _check_one(item, value_type)
            for key, item in value.items()
        )

    if origin is tuple:
        if not isinstance(value, tuple):
            return False
        if not args:
            #? A bare Tuple/tuple accepts any tuple. The empty-tuple type
            #? ``Tuple[()]``/``tuple[()]`` also resolves to empty ``args`` but
            #? is a distinct object; it must accept only ``()``.
            #? `t.Tuple` (the typing alias) and the builtin `tuple` are
            #? distinct objects; both must be accepted as a bare tuple.
            #? UP006 is suppressed because the typing alias is semantically
            #? required here, not a mere style preference.
            if annotation is t.Tuple or annotation is tuple:  # noqa: UP006
                return True
            return len(value) == 0
        if args == ((),):
            return len(value) == 0
        if len(args) == 2 and args[1] is Ellipsis:
            return all(_check_one(item, args[0]) for item in value)
        return len(value) == len(args) and all(
            _check_one(item, expected)
            for item, expected in zip(value, args, strict=True)
        )

    if origin in (set, frozenset):
        if not isinstance(value, origin):
            return False
        return not args or all(_check_one(item, args[0]) for item in value)

    if origin is cabc.Callable:
        return callable(value)

    try:
        return isinstance(value, origin)
    except TypeError:
        #? Unsupported typing constructs intentionally remain pass-through.
        return True


def _safe_args_repr(
    exc: Exception,
) -> str:
    """Describe a bind failure without reproducing value-bearing details.

    Parameters
    ----------
    exc : Exception
        exc parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    return f"{type(exc).__name__}: argument binding failed"


def _validate_type_checked_args(
    f: t.Callable,
    sig: inspect.Signature,
    hints: dict[str, t.Any],
    args: tuple[t.Any, ...],
    kw: dict[str, t.Any],
) -> None:
    """Validate ``args``/``kw`` against ``f``'s annotations, raising on error.

    Shared by the synchronous and asynchronous wrappers produced by
    ``type_checked`` so both validate arguments eagerly.
    """
    try:
        bound = sig.bind(*args, **kw)
    except TypeError as e:
        raise TypeError(
            f"Validation error in '{f.__name__}':\n{_safe_args_repr(e)}"
        ) from None

    errors: list[str] = []
    for name, param in sig.parameters.items():
        ann = hints.get(name, param.annotation)
        if ann is inspect.Parameter.empty:
            continue
        if name not in bound.arguments:
            continue
        value = bound.arguments[name]

        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            for idx, elem in enumerate(value):
                if not _check_one(elem, ann):
                    input_type = type(elem).__name__
                    errors.append(
                        f"Argument '{name}[{idx}]': expected {ann!r} "
                        f"(got type '{input_type}')"
                    )
            continue

        if param.kind is inspect.Parameter.VAR_KEYWORD:
            for k, v in value.items():
                if not _check_one(v, ann):
                    input_type = type(v).__name__
                    errors.append(
                        f"Argument '{name}[{k!r}]': expected {ann!r} "
                        f"(got type '{input_type}')"
                    )
            continue

        if not _check_one(value, ann):
            input_type = type(value).__name__
            errors.append(
                f"Argument '{name}': expected {ann!r} (got type '{input_type}')"
            )

    if errors:
        raise TypeError(
            f"Validation error in '{f.__name__}':\n" + "\n".join(errors)
        ) from None


def type_checked(
    func: t.Callable | None = None,
    **kwargs: t.Any,
) -> t.Callable:
    """type_checked() function.

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
    if kwargs:
        options = ", ".join(sorted(kwargs))
        raise TypeError(
            "stdlib type_checked does not support validator options: "
            f"{options}"
        )

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
        try:
            hints = t.get_type_hints(f)
        except Exception:
            hints = getattr(f, "__annotations__", {}) or {}
        sig = inspect.signature(f)

        if asyncio.iscoroutinefunction(f):
            #? Preserve coroutine-function identity on an async target so
            #? async-aware dispatchers (FastAPI, pytest-asyncio, etc.) that
            #? branch on iscoroutinefunction still treat the wrapped callable
            #? as async. Validate arguments eagerly (before await), then await
            #? the wrapped function so its result is returned, not an unawaited
            #? coroutine object.
            @functools.wraps(f)
            async def async_wrapper(
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
                _validate_type_checked_args(f, sig, hints, args, kw)
                return await f(*args, **kw)

            return async_wrapper

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
            _validate_type_checked_args(f, sig, hints, args, kw)
            return f(*args, **kw)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
