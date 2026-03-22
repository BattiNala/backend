"""
Schemas for citizen-related data models.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class CitizenBase(BaseModel):
    """Base schema for citizen information."""

    name: str = Field(..., max_length=100)
    email: Optional[EmailStr] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20, min_length=10)
    address: str = Field(None, max_length=200)


class CitizenCreate(CitizenBase):
    """Schema for creating a new citizen."""


class CitizenUpdate(CitizenBase):
    """Schema for updating citizen information."""

    email: Optional[EmailStr] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20, min_length=10)


class CitizenTrustScoreUpdate(BaseModel):
    """Schema for updating citizen trust score."""

    citizen_id: int
    trust_score: int


class CitizenProfile(BaseModel):
    """Schema for representing a citizen's profile."""

    name: str
    email: Optional[EmailStr]
    phone_number: Optional[str]
    address: Optional[str]
    trust_score: int
