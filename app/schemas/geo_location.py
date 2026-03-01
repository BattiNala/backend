from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")

    class Config:
        json_schema_extra = {"example": {"latitude": 40.7128, "longitude": -74.0060}}
