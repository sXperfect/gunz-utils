"""Stdlib-only analog of `gunz_utils.ext.validation_pydantic.type_checked`.

No pydantic import. Validates parameter annotations against actual call
args at runtime using `inspect.signature` + `isinstance` + `typing.get_origin`.
Raises `TypeError` on type mismatch with a value-redacted message.

Coverage:
  - Bare classes (int, str, list, dict, tuple, set, bool, etc.)
  - `Optional[X]` / `X | None` / `Union[X, ...]`
  - `*args: T` → each element validated against T
  - `**kw: T`  → each value validated against T
  - Container generics (list[X], dict[K, V], tuple[...]) → origin only

Unsupported (treated as a pass): custom `Annotated` metadata, generic
aliases, TypeVar resolution.
"""
from __future__ import annotations

import functools
import inspect
import typing as t

__all__ = ["type_checked"]


def _check_one(value: t.Any, annotation: t.Any) -> bool:
    origin = t.get_origin(annotation)
    if origin is None:
        if not isinstance(annotation, type):
            return True
        if annotation is int and isinstance(value, bool):
            return False
        return isinstance(value, annotation)

    if origin is t.Union:
        return any(_check_one(value, arg) for arg in t.get_args(annotation))

    if origin in (list, dict, tuple, set, frozenset):
        try:
            return isinstance(value, origin)
        except TypeError:
            return True

    return True


def _safe_args_repr(exc: Exception) -> str:
    msg = str(exc)
    return f"{type(exc).__name__}: {msg.splitlines()[0] if msg else 'argument binding failed'}"


def type_checked(
    func: t.Callable | None = None,
    **kwargs: t.Any,
) -> t.Callable:
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
                                f"Argument '{name}[{idx}]': expected {ann!r} (got type '{input_type}')"
                            )
                    continue

                if param.kind is inspect.Parameter.VAR_KEYWORD:
                    for k, v in value.items():
                        if not _check_one(v, ann):
                            input_type = type(v).__name__
                            errors.append(
                                f"Argument '{name}[{k!r}]': expected {ann!r} (got type '{input_type}')"
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