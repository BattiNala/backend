"""
Schemas for team-related data models.
"""

from pydantic import BaseModel, Field


class TeamBase(BaseModel):
    """Base schema for team information."""

    team_name: str = Field(..., max_length=100)
    status: bool = Field(..., description="Availability status of the team")
    department_id: int = Field(..., description="ID of the department the team belongs to")
    base_latitude: str = Field(..., max_length=50)
    base_longitude: str = Field(..., max_length=50)
    coverage_radius_km: int = Field(..., description="Coverage radius in kilometers")


class TeamCreate(TeamBase):
    """Schema for creating a new team."""


class TeamUpdate(BaseModel):
    """Schema for updating team information."""

    team_name: str = Field(None, max_length=100)
    status: bool = Field(None, description="Availability status of the team")
    # department_id: int = Field(
    #     None, description="ID of the department the team belongs to"
    # )
    base_latitude: str = Field(None, max_length=50)
    base_longitude: str = Field(None, max_length=50)
    coverage_radius_km: int = Field(None, description="Coverage radius in kilometers")


class TeamChangeStatus(BaseModel):
    """Schema for changing team status."""

    team_id: int = Field(..., description="ID of the team to change status")
    status: bool = Field(..., description="New status of the team")


class Team(TeamBase):
    """Schema for team information returned in responses."""

    team_id: int
    model_config = {"from_attributes": True}


class TeamList(BaseModel):
    """Schema for listing multiple teams."""

    teams: list[Team]
