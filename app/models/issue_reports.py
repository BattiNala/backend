"""Issue model definition."""

# pylint: disable=not-callable

from sqlalchemy import (
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
class IssueReport(Base):  # pylint: disable=too-few-public-methods
    """Model representing an issue report submitted by a citizen."""

    __tablename__ = "issue_reports"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(
        Integer,
        ForeignKey("issues.issue_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    description = Column(String(1000), nullable=False)
    reported_by = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
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
    issue = relationship("Issue", back_populates="reported_issue_reports")
    reporter = relationship("Employee", back_populates="reported_issue_reports")
