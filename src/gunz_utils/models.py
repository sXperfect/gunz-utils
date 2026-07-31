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
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "Clear BSD"
__version__ = "1.3.2"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from pydantic import BaseModel, ConfigDict


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

