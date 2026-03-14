"""Issue model definition."""

# pylint: disable=not-callable

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.schemas.issue import IssueStatus


class Issue(Base):  # pylint: disable=too-few-public-methods
    """Model representing an issue reported by a citizen."""

    __tablename__ = "issues"

    issue_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_label = Column(String(100), nullable=True, unique=True)
    issue_type = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description = Column(String(1000), nullable=False)
    status = Column(SQLEnum(IssueStatus, name="issue_status_enum"), nullable=False)
    is_anonymous = Column(Boolean, default=False, nullable=False)
    contact_no = Column(String(20), nullable=True)
    reporter_id = Column(
        Integer,
        ForeignKey("citizens.citizen_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    assignee_id = Column(
        Integer,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reporter = relationship("Citizen", back_populates="reported_issues", foreign_keys=[reporter_id])
    assignee = relationship(
        "Employee", back_populates="assigned_issues", foreign_keys=[assignee_id]
    )
    department = relationship("Department", back_populates="issues", foreign_keys=[issue_type])

    issue_location = relationship(
        "IssueLocation",
        back_populates="issue",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    attachments = relationship(
        "Attachment",
        back_populates="issue",
        cascade="all, delete-orphan",
        single_parent=True,
    )
