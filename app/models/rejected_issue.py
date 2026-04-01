"""Issue model definition."""

# pylint: disable=not-callable

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# pylint: disable=duplicate-code
class RejectedIssue(Base):  # pylint: disable=too-few-public-methods
    """Model representing a rejected issue."""

    __tablename__ = "rejected_issues"

    reject_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(
        Integer,
        ForeignKey("issues.issue_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    rejected_by = Column(
        Integer, ForeignKey("employees.employee_id", ondelete="SET NULL"), nullable=True
    )
    auto_rejected = Column(Boolean, default=False, nullable=False)
    reason = Column(String(1000), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    issue = relationship("Issue", back_populates="rejected_issues")
    rejected_by_employee = relationship("Employee", back_populates="rejected_issues")
