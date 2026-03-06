"""
Schemas for citizen-related data models.
"""

from typing import Optional
from pydantic import BaseModel, Field


class CitizenBase(BaseModel):
    """Base schema for citizen information."""

    name: str = Field(..., max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    address: str = Field(None, max_length=200)


class CitizenCreate(CitizenBase):
    """Schema for creating a new citizen."""


class CitizenUpdate(CitizenBase):
    """Schema for updating citizen information."""

    email: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)


class CitizenTrustScoreUpdate(BaseModel):
    """Schema for updating citizen trust score."""

    citizen_id: int
    trust_score: int
