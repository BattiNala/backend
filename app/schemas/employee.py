"""
Schemas for employee-related data models.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class EmployeeActivityStatus(str, Enum):
    """Enumeration for employee activity status."""

    BUSY = "busy"
    AVAILABLE = "available"
    OFF_DUTY = "off_duty"


class EmployeeBase(BaseModel):
    """Base schema for employee information."""

    name: str = Field(..., max_length=100)
    email: EmailStr
    phone_number: str = Field(..., max_length=20)
    team_id: Optional[int] = None
    current_status: EmployeeActivityStatus = EmployeeActivityStatus.AVAILABLE


class EmployeeCreate(EmployeeBase):
    """Schema for creating a new employee."""


class EmployeeUpdate(EmployeeBase):
    """Schema for updating employee information."""

    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)


class EmployeeTeamUpdate(BaseModel):
    """Schema for updating employee's team assignment."""

    employee_id: int
    team_id: int


class EmployeeStatusUpdate(BaseModel):
    """Schema for updating employee's activity status."""

    employee_id: int
    current_status: EmployeeActivityStatus


class EmployeeProfile(BaseModel):
    """Schema for representing an employee's profile."""

    name: str
    email: EmailStr
    phone_number: str
    team_name: Optional[str]
    department_name: str
    current_status: EmployeeActivityStatus


class EmployeeTeamChangeRequest(BaseModel):
    """Schema for requesting a change in an employee's team assignment."""

    employee_id: int
    new_team_id: int


class EmployeeCreateResponse(BaseModel):
    """Schema for the response after creating a new employee."""

    message: str
    employee_id: int
