"""
Schemas for role-related data models.
"""

from pydantic import BaseModel


class RoleBase(BaseModel):
    """Base schema for role information."""

    role_name: str


class RoleCreate(RoleBase):
    """Schema for creating a new role."""

class Role(RoleBase):
    """Schema for role information returned in responses."""

    role_id: int
    model_config = {"from_attributes": True}

class RoleList(BaseModel):
    """Schema for listing multiple roles."""

    roles: list[Role]