"""Schemas for department-related data models."""

from pydantic import BaseModel, EmailStr


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


class DepartmentAdminCreate(BaseModel):
    """Schema for creating a department admin."""

    department_id: int
    name: str
    email: str
    phone_number: str
    password: str


class DepartmentAdmin(BaseModel):
    """Schema for department admin information returned in responses."""

    employee_id: int
    user_id: int
    department_name: str
    name: str
    email: EmailStr
    phone_number: str
    team_id: int | None
    model_config = {"from_attributes": True}
