"""
DepartmentAdmin model definition.
"""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class DepartmentAdmin(Base):
    """
    Model representing a department administrator responsible for managing a department.
    Each department admin is associated with a specific department and has contact information.
    """

    __tablename__ = "department_admins"

    admin_id = Column(Integer, primary_key=True, autoincrement=True)
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

    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user = relationship("User", back_populates="department_admin_profile", foreign_keys=[user_id])
    department = relationship(
        "Department", back_populates="department_admins", foreign_keys=[department_id]
    )

    def __repr__(self):
        return f"""
        <DepartmentAdmin(admin_id={self.admin_id}, name='{self.name}', email='{self.email}')>
        """
