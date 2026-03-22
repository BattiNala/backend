"""Schemas for route planning."""

from pydantic import BaseModel, Field

from app.schemas.geo_location import GeoLocation


class RouteRequest(BaseModel):
    """Request payload for shortest route query."""

    start: GeoLocation = Field(..., description="Start location")
    destination: GeoLocation = Field(..., description="Destination location")


class RouteResponse(BaseModel):
    """Response payload for shortest route query."""

    distance_km: float = Field(..., description="Shortest path distance in kilometers")
    path: list[GeoLocation] = Field(..., description="Final route geometry")
    snapped_start: GeoLocation | None = Field(
        None, description="Nearest routable graph node used for the start"
    )
    snapped_destination: GeoLocation | None = Field(
        None, description="Nearest routable graph node used for the destination"
    )
