"""
Shared data models for HyperHedron components.
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
from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Standardized health check response for MCP servers."""

    status: str = Field(..., description="HEALTHY or UNHEALTHY")
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
