from sqlalchemy import Column, Integer, String
from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), nullable=False, unique=True)

    def __repr__(self):
        return f"<Role(role_id={self.role_id}, role_name='{self.role_name}')>"
