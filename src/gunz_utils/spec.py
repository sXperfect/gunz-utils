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
    ValueError
        If both ``value`` and provided fields are supplied, or if ``value``
        is neither an instance of ``spec_cls``, a Mapping, nor None.
    """
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
    ValueError
        If any item is neither an instance of ``spec_cls`` nor a Mapping.
    """
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


__all__ = ["coerce_spec_sequence", "from_object_or_fields"]
