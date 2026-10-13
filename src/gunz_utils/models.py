"""
Shared data models for HyperHedron components.

Public surface
--------------

- :class:`GunzBaseModel` — shared Pydantic v2 base class with strict
  config defaults (``extra="forbid"``, ``str_strip_whitespace=True``,
  ``validate_assignment=True``, ``frozen=False``). Subclass this for
  any domain model that wants consistent validation behavior across
  the workspace.
"""

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import types
import typing as t

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from pydantic import BaseModel, ConfigDict, model_validator

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__


def _annotation_is_int(
    annotation: object,
) -> bool:
    """Whether ``annotation`` is an ``int``-typed field (not ``bool``).

    ``bool`` is an ``int`` subclass, so a bare ``isinstance`` check cannot
    distinguish the two; this helper treats ``bool`` (and ``bool``-only
    unions) as non-``int`` while accepting ``int``, ``int | None``, and
    ``Literal[int, ...]`` fields.
    """
    if annotation is int:
        return True
    if annotation is bool:
        return False
    if annotation is None:
        return False
    origin = t.get_origin(annotation)
    args = getattr(annotation, "__args__", ())
    if origin in (t.Union, types.UnionType):
        return any(_annotation_is_int(arg) for arg in args)
    if origin is t.Literal:
        #? A Literal restricted to int literals is an int-typed field; a bool
        #? supplied to it must still be rejected.
        return bool(args) and all(
            isinstance(arg, int) and not isinstance(arg, bool) for arg in args
        )
    return False


class GunzBaseModel(BaseModel):
    """Shared Pydantic v2 base for HyperHedron domain models.

    Encapsulates the three strictness settings that every
    workspace model wants by default:

    - ``extra="forbid"`` — unknown fields raise ``ValidationError``
      instead of silently being ignored. Catches typo bugs at the
      data-construction boundary.
    - ``str_strip_whitespace=True`` — string fields are
      whitespace-trimmed on assignment. Matches the convention used
      by every model that ingests user / LLM-supplied content.
    - ``validate_assignment=True`` — mutating an instance attribute
      after construction re-runs the field validator. Catches
      mutation bugs that would otherwise bypass validation.

    Override any of these in a subclass by re-declaring
    ``model_config = ConfigDict(...)``. Pydantic v2 merges subclass
    configs with the parent class, with subclass taking precedence.

    Examples
    --------
    >>> from gunz_utils import GunzBaseModel
    >>> class MyRecord(GunzBaseModel):
    ...     name: str
    ...
    >>> MyRecord(name="  hi  ").name
    'hi'
    >>> MyRecord(name="x", extra_field=1)
    Traceback (most recent call last):
        ...
    pydantic_core._pydantic_core.ValidationError: ...
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_bool_for_int_fields(cls, data: object) -> object:
        """Reject a Python ``bool`` supplied for an ``int``-typed field.

        Pydantic's lax mode silently coerces ``bool`` into ``int`` (and vice
        versa), which contradicts the strict config defaults and the package's
        bool-vs-int separation. This narrow guard rejects a ``bool`` for an
        ``int`` field while leaving legitimate ``str`` -> ``int`` coercion
        intact. ``bool``-typed fields are unaffected.
        """
        if not isinstance(data, dict):
            return data
        for name, field in cls.model_fields.items():
            if name not in data:
                continue
            if _annotation_is_int(field.annotation) and isinstance(data[name], bool):
                raise ValueError(f"field {name!r} must be an int, got bool")
        return data


__all__ = ["GunzBaseModel"]
