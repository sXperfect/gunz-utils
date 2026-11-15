"""
Coerce a config spec from an object, a mapping, or individual fields.

A spec is a dataclass-style class that can be built from keyword arguments.
``from_object_or_fields`` lets callers supply it as an already-built instance,
a field mapping, or a set of explicit field values (with the ``UNSET`` sentinel
marking "not supplied"), and returns a single validated instance.
"""

from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .sentinels import UNSET

T = TypeVar("T")


class CoercionError(ValueError):
    """Raised when spec coercion fails."""


def validate_constraints(
    schema: Mapping[str, Any],
    data: Mapping[str, Any],
) -> list[str]:
    """Validate a dictionary against a constraint schema.

    Supported schema rules per field:
    - ``type``: expected Python type or tuple of types
    - ``required``: bool indicating whether field must be present
    - ``min``: minimum numerical value (inclusive)
    - ``max``: maximum numerical value (inclusive)
    - ``min_len``: minimum length of sequence/string
    - ``max_len``: maximum length of sequence/string
    - ``allowed``: iterable of allowed values

    Returns
    -------
    list[str]
        List of validation error messages. Empty list indicates valid data.
    """
    errors: list[str] = []

    for field, rules in schema.items():
        if not isinstance(rules, Mapping):
            continue

        is_required = rules.get("required", False)
        if field not in data or data[field] is None:
            if is_required:
                errors.append(f"field '{field}' is required")
            continue

        val = data[field]

        #? Type check
        expected_type = rules.get("type")
        if expected_type is not None and not isinstance(val, expected_type):
            errors.append(
                f"field '{field}' expected type {expected_type}, got {type(val).__name__}"
            )
            continue

        #? Min / Max numeric value
        if "min" in rules and isinstance(val, (int, float)) and val < rules["min"]:
            errors.append(f"field '{field}' ({val}) is less than minimum {rules['min']}")
        if "max" in rules and isinstance(val, (int, float)) and val > rules["max"]:
            errors.append(f"field '{field}' ({val}) exceeds maximum {rules['max']}")

        #? Min / Max length
        if "min_len" in rules and hasattr(val, "__len__") and len(val) < rules["min_len"]:
            errors.append(f"field '{field}' length ({len(val)}) is less than minimum {rules['min_len']}")
        if "max_len" in rules and hasattr(val, "__len__") and len(val) > rules["max_len"]:
            errors.append(f"field '{field}' length ({len(val)}) exceeds maximum {rules['max_len']}")

        #? Allowed values
        if "allowed" in rules and val not in rules["allowed"]:
            errors.append(f"field '{field}' value {val!r} is not in allowed set {rules['allowed']!r}")

    return errors


def from_object_or_fields(
    spec_cls: type[T],
    value: T | Mapping[str, Any] | None,
    fields: Mapping[str, Any],
    *,
    allow_none: bool = False,
) -> T | None:
    """Build a config spec from an object, a mapping, or individual fields.

    ``UNSET`` entries in ``fields`` are ignored, so the same mapping may carry
    a mix of supplied values and "not provided" markers. Supplying both
    ``value`` and any provided field raises, as does an unsupported ``value``
    type.

    Parameters
    ----------
    spec_cls : type
        Spec class constructible from keyword arguments (e.g. a frozen
        dataclass such as ``PatchSpec`` or ``LoaderSpec``).
    value : spec_cls or Mapping or None
        The spec as an instance or field mapping, or None to build it from
        ``fields``.
    fields : Mapping of str to object
        Individual field values; ``UNSET`` entries are treated as not
        supplied.
    allow_none : bool, optional
        Whether to return None when neither ``value`` nor any provided field
        is supplied, used when a spec has a meaningful default of None.
        Defaults to False.

    Returns
    -------
    spec_cls or None
        A validated spec instance; None only when ``allow_none`` is True and
        nothing was supplied.

    Raises
    ------
    TypeError
        If ``spec_cls`` is not a type, ``fields`` is not a Mapping, or
        ``allow_none`` is not a bool.
    ValueError
        If both ``value`` and provided fields are supplied, or if ``value``
        is neither an instance of ``spec_cls``, a Mapping, nor None.
    """
    if not isinstance(spec_cls, type):
        raise TypeError(f"spec_cls must be a type, got {type(spec_cls).__name__}")
    if not isinstance(fields, Mapping):
        raise TypeError(f"fields must be a Mapping, got {type(fields).__name__}")
    if not isinstance(allow_none, bool):
        raise TypeError("allow_none must be a bool")
    provided = {
        key: item
        for key, item in fields.items()
        if item is not UNSET
    }
    if value is not None and provided:
        raise ValueError(
            f"Supply either the {spec_cls.__name__} object or its individual "
            "arguments, not both."
        )
    if value is not None:
        if isinstance(value, spec_cls):
            return value
        if isinstance(value, Mapping):
            return spec_cls(**value)
        raise ValueError(
            f"{spec_cls.__name__} must be an instance, a mapping of its "
            "fields, or None."
        )
    if provided:
        return spec_cls(**provided)
    if allow_none:
        return None
    return spec_cls()


def coerce_spec_sequence(
    spec_cls: type[T],
    items: Iterable[T | Mapping[str, Any]],
) -> tuple[T, ...]:
    """Coerce each item of a sequence into a validated spec instance.

    Each item may already be an instance of ``spec_cls`` or a field mapping;
    both are normalized to a validated spec. This lets callers accept either
    pre-built specs or plain field dictionaries for a sequence of configs.

    Parameters
    ----------
    spec_cls : type
        Spec class constructible from keyword arguments (e.g. a frozen
        dataclass such as ``SourceSpec`` or ``Recipe``).
    items : Iterable of spec_cls or Mapping
        Sequence whose items are specs or field mappings.

    Returns
    -------
    tuple of spec_cls
        A tuple with every item coerced to a validated spec.

    Raises
    ------
    TypeError
        If ``spec_cls`` is not a type or ``items`` is a string or bytes.
    ValueError
        If any item is neither an instance of ``spec_cls`` nor a Mapping.
    """
    if not isinstance(spec_cls, type):
        raise TypeError(f"spec_cls must be a type, got {type(spec_cls).__name__}")
    if isinstance(items, (str, bytes, bytearray)):
        raise TypeError("items must be an iterable of specs or mappings, not string or bytes")
    coerced = []
    for item in items:
        if isinstance(item, spec_cls):
            coerced.append(item)
        elif isinstance(item, Mapping):
            coerced.append(spec_cls(**item))
        else:
            raise ValueError(
                f"{spec_cls.__name__} sequence items must be instances or "
                "field mappings."
            )
    return tuple(coerced)


def coerce_spec_mapping(
    spec_cls: type[T],
    mapping: Mapping[str, T | Mapping[str, Any]],
) -> dict[str, T]:
    """Coerce each value in a mapping into a validated spec instance.

    Parameters
    ----------
    spec_cls : type
        Spec class constructible from keyword arguments.
    mapping : Mapping
        Mapping whose values are spec instances or field mappings.

    Returns
    -------
    dict[str, T]
        Mapping with values coerced to validated spec instances.
    """
    if not isinstance(spec_cls, type):
        raise TypeError(f"spec_cls must be a type, got {type(spec_cls).__name__}")
    if not isinstance(mapping, Mapping):
        raise TypeError(f"mapping must be a Mapping, got {type(mapping).__name__}")
    result: dict[str, T] = {}
    for key, item in mapping.items():
        if isinstance(item, spec_cls):
            result[key] = item
        elif isinstance(item, Mapping):
            result[key] = spec_cls(**item)
        else:
            raise ValueError(
                f"{spec_cls.__name__} mapping values must be instances or "
                f"field mappings, got {type(item).__name__}."
            )
    return result


__all__ = [
    "CoercionError",
    "coerce_spec_mapping",
    "coerce_spec_sequence",
    "from_object_or_fields",
    "validate_constraints",
]
