from sqlalchemy import Column, Integer, String
from app.db.base import Base


class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True, autoincrement=True)
    department_name = Column(String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"<Department(department_id={self.department_id}, department_name='{self.department_name}')>"
