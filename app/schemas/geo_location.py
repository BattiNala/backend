"""
Schemas for geo-location related data models.
"""

from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    """Schema for geographic location coordinates."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic model configuration for schema examples."""

        json_schema_extra = {"example": {"latitude": 40.7128, "longitude": -74.0060}}
