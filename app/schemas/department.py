"""
Schemas for department-related data models.
"""

from pydantic import BaseModel

class DepartmentBase(BaseModel):
    """Base schema for department information."""

    department_name: str


class DepartmentCreate(DepartmentBase):
    """Schema for creating a new department."""

class Department(DepartmentBase):
    """Schema for department information returned in responses."""

    department_id: int
    model_config = {"from_attributes": True}

class DepartmentList(BaseModel):
    """Schema for listing multiple departments."""

    departments: list[Department]