from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base


class Attachment(Base):
    __tablename__ = "attachments"

    attachment_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(
        Integer, ForeignKey("issues.issue_id", ondelete="CASCADE"), nullable=False
    )
    path = Column(String(255), nullable=False)

    issue = relationship("Issue", back_populates="attachments", foreign_keys=[issue_id])

    def __repr__(self):
        return f"<Attachment(attachment_id={self.attachment_id}, issue_id={self.issue_id}, path='{self.path}')>"
