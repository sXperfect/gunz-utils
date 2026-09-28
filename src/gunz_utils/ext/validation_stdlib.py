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
from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
import functools
import inspect
import types
import typing as t

from .._version import __version__ as __version__

__all__ = ["type_checked"]


def _check_one(value: t.Any, annotation: t.Any) -> bool:
    """Recursively validate the runtime subset promised by this backend."""
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
            return True
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
        # Unsupported typing constructs intentionally remain pass-through.
        return True


def _safe_args_repr(exc: Exception) -> str:
    msg = str(exc)
    head_line = msg.splitlines()[0] if msg else "argument binding failed"
    return f"{type(exc).__name__}: {head_line}"


def type_checked(
    func: t.Callable | None = None,
    **kwargs: t.Any,
) -> t.Callable:
    if kwargs:
        options = ", ".join(sorted(kwargs))
        raise TypeError(
            "stdlib type_checked does not support validator options: "
            f"{options}"
        )

    def decorator(f: t.Callable) -> t.Callable:
        try:
            hints = t.get_type_hints(f)
        except Exception:
            hints = getattr(f, "__annotations__", {}) or {}
        sig = inspect.signature(f)

        @functools.wraps(f)
        def wrapper(*args: t.Any, **kw: t.Any) -> t.Any:
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

            return f(*args, **kw)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
