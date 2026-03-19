"""OTP code model definition."""

# pylint: disable=not-callable

from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.schemas.otp import OtpChannel, OtpPurpose


def _enum_values(enum_cls):
    """Persist enum values to Postgres so they match the existing DB enum labels."""
    return [member.value for member in enum_cls]


class OtpCode(Base):  # pylint: disable=too-few-public-methods
    """One-time password request and verification metadata."""

    __tablename__ = "otp_codes"

    otp_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=True,
    )

    channel = Column(
        Enum(OtpChannel, name="otp_channel", values_callable=_enum_values),
        nullable=False,
    )

    target = Column(
        String(255),
        nullable=False,
    )

    purpose = Column(
        Enum(OtpPurpose, name="otp_purpose", values_callable=_enum_values),
        nullable=False,
    )

    otp_salt = Column(
        LargeBinary,
        nullable=False,
    )

    otp_hash = Column(
        LargeBinary,
        nullable=False,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    resend_available_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    attempts_left = Column(
        Integer,
        nullable=False,
        default=5,
    )

    consumed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    request_ip = Column(
        INET,
        nullable=True,
    )

    user_agent = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="otp_codes", foreign_keys=[user_id])
