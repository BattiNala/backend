"""Attachment model definition."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Attachment(Base):  # pylint: disable=too-few-public-methods
    """File attachment metadata for an issue."""

    __tablename__ = "attachments"

    attachment_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("issues.issue_id", ondelete="CASCADE"), nullable=False)
    path = Column(String(255), nullable=False)

    issue = relationship("Issue", back_populates="attachments", foreign_keys=[issue_id])

    def __repr__(self):
        return (
            "<Attachment("
            f"attachment_id={self.attachment_id}, "
            f"issue_id={self.issue_id}, "
            f"path='{self.path}'"
            ")>"
        )
