from sqlalchemy import Column, Integer, String, ForeignKey, Enum as sql_enum
from sqlalchemy.orm import relationship
from enum import Enum
from app.db.base import Base


class ActivityStatus(str, Enum):
    BUSY = "busy"
    AVAILABLE = "available"
    OFF_DUTY = "off_duty"


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    phone_number = Column(String(20), nullable=False, unique=True)

    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    team_id = Column(
        Integer,
        ForeignKey("teams.team_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_status = Column(
        sql_enum(ActivityStatus, name="activity_status_enum"),
        nullable=False,
        default=ActivityStatus.AVAILABLE,
    )

    user = relationship("User", back_populates="employee_profile", uselist=False)

    assigned_issues = relationship(
        "Issue",
        back_populates="assignee",
        foreign_keys="Issue.assignee_id",
    )
