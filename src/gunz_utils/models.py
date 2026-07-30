"""
Shared data models for HyperHedron components.

Public surface
--------------

- :class:`GunzBaseModel` — shared Pydantic v2 base class with strict
  config defaults (``extra="forbid"``, ``str_strip_whitespace=True``,
  ``validate_assignment=True``, ``frozen=False``). Subclass this for
  any domain model that wants consistent validation behavior across
  the workspace.

- :class:`HealthStatus` — standardized MCP-server health-check response.
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
from datetime import datetime
from typing import Any

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from pydantic import BaseModel, ConfigDict, Field


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


class HealthStatus(BaseModel):
    """Standardized health check response for MCP servers."""

    status: str = Field(
        "UNKNOWN",
        description="HEALTHY or UNHEALTHY (defaults to UNKNOWN until checked)",
    )
    message: str | None = Field(
        None,
        description="Detailed status or error message",
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str | None = None
    hostname: str = Field(default_factory=lambda: __import__("os").uname().nodename)
    checks: dict[str, Any] = Field(
        default_factory=dict,
        description="Component-specific health signals",
    )
