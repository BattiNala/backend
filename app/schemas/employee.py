from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum


class EmployeeActivityStatus(str, Enum):
    BUSY = "busy"
    AVAILABLE = "available"
    OFF_DUTY = "off_duty"


class EmployeeBase(BaseModel):
    name: str = Field(..., max_length=100)
    email: EmailStr
    phone_number: str = Field(..., max_length=20)
    team_id: Optional[int] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(EmployeeBase):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)


class EmployeeTeamUpdate(BaseModel):
    employee_id: int
    team_id: int


class EmployeeStatusUpdate(BaseModel):
    employee_id: int
    current_status: EmployeeActivityStatus
