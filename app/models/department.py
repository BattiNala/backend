"""Department model definition."""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Department(Base):  # pylint: disable=too-few-public-methods
    """Department grouping for teams."""

    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True, autoincrement=True)
    department_name = Column(String(100), nullable=False, unique=True)
    teams = relationship("Team", back_populates="department", cascade="all, delete-orphan")
    department_admins = relationship(
        "DepartmentAdmin", back_populates="department", cascade="all, delete-orphan"
    )
    issues = relationship("Issue", back_populates="department", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            "<Department("
            f"department_id={self.department_id}, "
            f"department_name='{self.department_name}'"
            ")>"
        )
