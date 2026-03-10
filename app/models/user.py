"""User model definition."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):  # pylint: disable=too-few-public-methods
    """Application user credentials and role mapping."""

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(128), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False)
    status = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)

    role = relationship("Role", back_populates="users", foreign_keys=[role_id])
    citizen_profile = relationship(
        "Citizen",
        back_populates="user",
        uselist=False,
    )
    employee_profile = relationship(
        "Employee",
        back_populates="user",
        uselist=False,
    )
    otp_codes = relationship("OtpCode", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            "<User("
            f"user_id={self.user_id}, "
            f"username='{self.username}', "
            f"role_id={self.role_id}, "
            f"status={self.status}, "
            f"is_verified={self.is_verified}"
            ")>"
        )
