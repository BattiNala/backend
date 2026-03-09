"""IssueLocation model definition."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class IssueLocation(Base):  # pylint: disable=too-few-public-methods
    """Model representing the location details of an issue."""

    __tablename__ = "issue_locations"

    location_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(
        Integer,
        ForeignKey("issues.issue_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    latitude = Column(String(50), nullable=False)
    longitude = Column(String(50), nullable=False)
    address = Column(String(255), nullable=True)

    issue = relationship(
        "Issue",
        back_populates="issue_location",
        foreign_keys=[issue_id],
    )

    def __repr__(self):
        return (
            f"IssueLocation(location_id={self.location_id}, issue_id={self.issue_id},"
            f"latitude='{self.latitude}', longitude='{self.longitude}', address='{self.address}')"
        )
