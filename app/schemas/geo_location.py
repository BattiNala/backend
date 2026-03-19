"""Schemas for geo-location related data models."""

from pydantic import BaseModel, ConfigDict, Field


class GeoLocation(BaseModel):
    """Schema for geographic location coordinates."""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    model_config = ConfigDict(
        json_schema_extra={"example": {"latitude": 40.7128, "longitude": -74.0060}}
    )
