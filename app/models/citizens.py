"""Citizen model definition."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class Citizen(Base):  # pylint: disable=too-few-public-methods
    """Citizen profile linked to a user account."""
    __tablename__ = "citizens"

    citizen_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True, unique=True)
    phone_number = Column(String(20), nullable=True, unique=True)
    home_address = Column(String(200), nullable=False)
    trust_score = Column(Integer, default=0)

    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        unique=True,
    )

    user = relationship("User", back_populates="citizen_profile", uselist=False)

    # reported_issues = relationship(
    #     "Issue",
    #     back_populates="reporter",
    #     foreign_keys="Issue.reporter_id",
    # )

    def __repr__(self):
        return (
            "<Citizen("
            f"citizen_id={self.citizen_id}, "
            f"name='{self.name}', "
            f"email='{self.email}', "
            f"phone_number='{self.phone_number}', "
            f"home_address='{self.home_address}', "
            f"trust_score={self.trust_score}"
            ")>"
        )
