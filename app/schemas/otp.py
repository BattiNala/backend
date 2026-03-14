"""
Schemas for OTP-related data models.
"""

import enum
from datetime import datetime

from pydantic import BaseModel


class OtpChannel(enum.Enum):
    """Enumeration for OTP delivery channels."""

    SMS = "sms"
    EMAIL = "email"


class OtpPurpose(enum.Enum):
    """Enumeration for OTP purposes."""

    SIGNUP = "signup"
    RESET_PASSWORD = "reset_password"
    ANON_REPORT = "anon_report"
    OTHER = "other"


class OtpCodeBase(BaseModel):
    """Base schema for OTP code information."""

    user_id: int
    code: str
    channel: OtpChannel
    purpose: OtpPurpose
    expires_at: datetime


class OtpVerificationRequest(BaseModel):
    """Schema for OTP verification request."""

    code: str
