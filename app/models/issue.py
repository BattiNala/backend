from enum import Enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum as SQLEnum,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class IssueType(str, Enum):
    ELECTRICITY = "ELECTRICITY"
    SEWAGE = "SEWAGE"


class IssueStatus(str, Enum):
    REJECTED = "REJECTED"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class Issue(Base):
    __tablename__ = "issues"

    issue_id = Column(Integer, primary_key=True, autoincrement=True)
    issue_type = Column(SQLEnum(IssueType, name="issue_type_enum"), nullable=False)
    description = Column(String(1000), nullable=False)
    status = Column(SQLEnum(IssueStatus, name="issue_status_enum"), nullable=False)
    is_anonymous = Column(bool, default=False, nullable=False)
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

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reporter = relationship(
        "Citizen", back_populates="reported_issues", foreign_keys=[reporter_id]
    )
    assignee = relationship(
        "Employee", back_populates="assigned_issues", foreign_keys=[assignee_id]
    )
    # attachments = relationship(
    #     "Attachment", back_populates="issue", cascade="all, delete-orphan"
    # )
