# schemas for citizen related data models

from pydantic import BaseModel, Field
from typing import Optional


class CitizenBase(BaseModel):
    name: str = Field(..., max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    address: str = Field(None, max_length=200)


class CitizenCreate(CitizenBase):
    pass


class CitizenUpdate(CitizenBase):
    email: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)


class CizenTrustScoreUpdate(BaseModel):
    citizen_id: int
    trust_score: int
