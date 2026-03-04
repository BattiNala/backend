from sqlalchemy import Column, Integer, String
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(128), nullable=False)
    role_id = Column(Integer, nullable=False)
    status = Column(bool, nullable=False, default=True)
    is_verified = Column(bool, nullable=False, default=False)

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}', role_id={self.role_id}, status={self.status}, is_verified={self.is_verified})>"
