# -*- coding: utf-8 -*-
"""
Shared data models for HyperHedron components.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class HealthStatus(BaseModel):
    """Standardized health check response for MCP servers."""
    status: str = Field(..., description="HEALTHY or UNHEALTHY")
    message: Optional[str] = Field(None, description="Detailed status or error message")
    timestamp: datetime = Field(default_factory=datetime.now)
    version: Optional[str] = None
    hostname: str = Field(default_factory=lambda: __import__('os').uname().nodename)
    checks: Dict[str, Any] = Field(default_factory=dict, description="Component-specific health signals")
