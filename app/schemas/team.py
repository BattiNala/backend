from pydantic import BaseModel, Field


class TeamBase(BaseModel):
    team_name: str = Field(..., max_length=100)
    status: bool = Field(..., description="Availability status of the team")
    department_id: int = Field(
        ..., description="ID of the department the team belongs to"
    )
    base_latitude: str = Field(..., max_length=50)
    base_longitude: str = Field(..., max_length=50)
    coverage_radius_km: int = Field(..., description="Coverage radius in kilometers")


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    team_name: str = Field(None, max_length=100)
    status: bool = Field(None, description="Availability status of the team")
    # department_id: int = Field(
    #     None, description="ID of the department the team belongs to"
    # )
    base_latitude: str = Field(None, max_length=50)
    base_longitude: str = Field(None, max_length=50)
    coverage_radius_km: int = Field(None, description="Coverage radius in kilometers")


class TeamChangeStatus(BaseModel):
    team_id: int = Field(..., description="ID of the team to change status")
    status: bool = Field(..., description="New status of the team")
