"""Employee model definition."""

from sqlalchemy import Column, Enum as sql_enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.schemas.employee import EmployeeActivityStatus as ActivityStatus


class Employee(Base):  # pylint: disable=too-few-public-methods
    """Employee profile for a user account."""

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
    teams = relationship(
        "Team",
        back_populates="members",
        cascade="all, delete",
    )
    user = relationship("User", back_populates="employee_profile", uselist=False)

    assigned_issues = relationship(
        "Issue",
        back_populates="assignee",
        foreign_keys="Issue.assignee_id",
    )
