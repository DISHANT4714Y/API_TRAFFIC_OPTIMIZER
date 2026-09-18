"""
Pydantic data models for the Mock External API.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status message")


class DataResponse(BaseModel):
    """Deterministic resource payload response model."""
    resource_id: str = Field(..., description="Requested resource identifier")
    data: Dict[str, Any] = Field(..., description="Payload data for the resource")
    served_at: str = Field(..., description="ISO 8601 timestamp when request was processed")
    request_id: str = Field(..., description="Unique sequential mock request ID")


class StatsResponse(BaseModel):
    """Statistics response model."""
    total_requests: int = Field(..., description="Total number of resource requests processed")
    uptime_seconds: float = Field(..., description="Uptime in seconds since server start")


class ResetResponse(BaseModel):
    """Response returned upon resetting statistics."""
    status: str = Field(..., description="Reset operation status")
    total_requests: int = Field(..., description="Reset counter value, should be 0")
