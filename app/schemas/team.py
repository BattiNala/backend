"""
Schemas for team-related data models.
"""

from pydantic import BaseModel, Field, model_validator


def validate_team_fields(values):
    """Validate coverage_radius_km, base_latitude, and base_longitude."""
    coverage_radius = int(values.get("coverage_radius_km"))
    base_latitude = (
        float(values.get("base_latitude")) if values.get("base_latitude") is not None else None
    )
    base_longitude = (
        float(values.get("base_longitude")) if values.get("base_longitude") is not None else None
    )

    if coverage_radius is not None and coverage_radius <= 0:
        raise ValueError("Coverage radius must be a positive integer.")

    if base_latitude is not None:
        if not -90 <= base_latitude <= 90:
            raise ValueError("Base latitude must be between -90 and 90.")

    if base_longitude is not None:
        if not -180 <= base_longitude <= 180:
            raise ValueError("Base longitude must be between -180 and 180.")

    return values


class TeamBase(BaseModel):
    """Base schema for team information."""

    team_name: str = Field(..., max_length=100)
    status: bool = Field(..., description="Availability status of the team")
    department_id: int = Field(..., description="ID of the department the team belongs to")
    base_latitude: float = Field(..., description="Base latitude of the team")
    base_longitude: float = Field(..., description="Base longitude of the team")
    coverage_radius_km: int = Field(..., description="Coverage radius in kilometers")


class TeamCreate(BaseModel):
    """Schema for creating a new team."""

    team_name: str = Field(..., max_length=100)
    base_latitude: float = Field(..., description="Base latitude of the team")
    base_longitude: float = Field(..., description="Base longitude of the team")
    coverage_radius_km: int = Field(..., description="Coverage radius in kilometers")

    @model_validator(mode="before")
    @classmethod
    def validate_details(cls, values):
        """Validate team fields before creating a new team."""
        return validate_team_fields(values)


class TeamUpdate(TeamCreate):
    """Schema for updating team information."""

    team_id: int = Field(..., description="ID of the team to update")
    status: bool = Field(None, description="Availability status of the team")

    @model_validator(mode="before")
    @classmethod
    def validate_details(cls, values):
        """Validate team fields before updating team information."""
        return validate_team_fields(values)


class TeamChangeStatus(BaseModel):
    """Schema for changing team status."""

    team_id: int = Field(..., description="ID of the team to change status")
    status: bool = Field(..., description="New status of the team")


class Team(TeamBase):
    """Schema for team information returned in responses."""

    team_id: int
    model_config = {"from_attributes": True}


class TeamDetail(Team):
    """Schema for detailed team information, including department name."""

    department_name: str = Field(..., description="Name of the department the team belongs to")


class TeamList(BaseModel):
    """Schema for listing multiple teams."""

    teams: list[TeamDetail]
