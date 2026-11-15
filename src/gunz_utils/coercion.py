"""Dynamic type coercion, schema normalization, and detailed conversion diagnostics."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


class CoercionError(ValueError):
    """Raised when value cannot be coerced into the target type."""

    def __init__(
        self,
        message: str,
        *,
        value: Any = None,
        target_type: type | None = None,
        field_path: str = "",
    ) -> None:
        super().__init__(message)
        self.value = value
        self.target_type = target_type
        self.field_path = field_path


def format_coercion_error(exc: CoercionError, path: str = "") -> str:
    """Format a CoercionError with hierarchical path details."""
    effective_path = path or exc.field_path or "<root>"
    return f"coercion error at '{effective_path}': {exc}"


def coerce_bool(value: Any) -> bool:
    """Coerce boolean values from strings, integers, or booleans."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "t", "on"):
            return True
        if v in ("false", "0", "no", "n", "f", "off"):
            return False
    raise CoercionError(f"cannot coerce {value!r} to bool", value=value, target_type=bool)


def coerce_int(value: Any) -> int:
    """Coerce integer values rejecting booleans and non-finite floats."""
    if isinstance(value, bool):
        raise CoercionError("boolean is not accepted as int", value=value, target_type=int)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CoercionError(f"cannot coerce non-finite float {value} to int", value=value, target_type=int)
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    raise CoercionError(f"cannot coerce {value!r} to int", value=value, target_type=int)


def coerce_float(value: Any, *, allow_nan: bool = False, allow_inf: bool = False) -> float:
    """Coerce floating-point values rejecting booleans."""
    if isinstance(value, bool):
        raise CoercionError("boolean is not accepted as float", value=value, target_type=float)
    if isinstance(value, (int, float)):
        val = float(value)
    elif isinstance(value, str):
        try:
            val = float(value.strip())
        except ValueError:
            raise CoercionError(f"cannot coerce {value!r} to float", value=value, target_type=float) from None
    else:
        raise CoercionError(f"cannot coerce {value!r} to float", value=value, target_type=float)

    if math.isnan(val) and not allow_nan:
        raise CoercionError("NaN is not allowed", value=value, target_type=float)
    if math.isinf(val) and not allow_inf:
        raise CoercionError("Infinity is not allowed", value=value, target_type=float)
    return val


def coerce_datetime(value: Any) -> datetime:
    """Coerce ISO formatted strings, integers (unix epoch), or datetimes."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    raise CoercionError(f"cannot coerce {value!r} to datetime", value=value, target_type=datetime)


def coerce_path(value: Any) -> Path:
    """Coerce strings or paths to a Path instance."""
    if isinstance(value, (str, Path)):
        return Path(value)
    raise CoercionError(f"cannot coerce {value!r} to Path", value=value, target_type=Path)


class CoercionRegistry:
    """Extensible registry of type coercers."""

    def __init__(self) -> None:
        self._coercers: dict[type, Callable[[Any], Any]] = {
            bool: coerce_bool,
            int: coerce_int,
            float: coerce_float,
            str: str,
            datetime: coerce_datetime,
            Path: coerce_path,
        }

    def register(self, target_type: type, coercer: Callable[[Any], Any]) -> None:
        """Register a custom coercer for a type."""
        self._coercers[target_type] = coercer

    def coerce(self, value: Any, target_type: type) -> Any:
        """Coerce value to target_type using registered coercers."""
        if value is None:
            return None
        if isinstance(value, target_type):
            return value
        coercer = self._coercers.get(target_type)
        if coercer is not None:
            return coercer(value)
        try:
            return target_type(value)
        except Exception as exc:
            raise CoercionError(
                f"failed to coerce {value!r} to {target_type.__name__}: {exc}",
                value=value,
                target_type=target_type,
            ) from exc


_DEFAULT_REGISTRY = CoercionRegistry()


def coerce_type(value: Any, target_type: type) -> Any:
    """Coerce a value to target_type using the default registry."""
    return _DEFAULT_REGISTRY.coerce(value, target_type)


def coerce_sequence(target_elem_type: type, items: Iterable[Any]) -> list[Any]:
    """Coerce all elements of an iterable to target_elem_type."""
    return [_DEFAULT_REGISTRY.coerce(item, target_elem_type) for item in items]


def coerce_mapping(
    schema: Mapping[str, type],
    data: Mapping[str, Any],
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Coerce dictionary values according to a field-to-type schema."""
    result: dict[str, Any] = {}
    for key, target_type in schema.items():
        if key in data:
            try:
                result[key] = _DEFAULT_REGISTRY.coerce(data[key], target_type)
            except CoercionError as exc:
                exc.field_path = key
                raise

    if strict:
        extra_keys = set(data.keys()) - set(schema.keys())
        if extra_keys:
            raise CoercionError(f"unexpected extra keys in data: {sorted(extra_keys)}")

    # Copy non-schema keys if not strict
    if not strict:
        for k, v in data.items():
            if k not in result:
                result[k] = v

    return result


__all__ = [
    "CoercionError",
    "CoercionRegistry",
    "coerce_bool",
    "coerce_datetime",
    "coerce_float",
    "coerce_int",
    "coerce_mapping",
    "coerce_path",
    "coerce_sequence",
    "coerce_type",
    "format_coercion_error",
]
