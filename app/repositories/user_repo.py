"""Repository helpers for `User` persistence and account state updates."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


class UserRepository:
    """Repository class for managing User entities in the database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> User:
        """Fetch a user by their ID, including their role information."""
        result = await self.db.execute(
            select(User).options(selectinload(User.role)).where(User.user_id == user_id)
        )
        return result.scalars().first()

    async def get_user_by_username(self, username: str) -> User:
        """Fetch a user by their username, including their role information."""
        result = await self.db.execute(
            select(User).options(selectinload(User.role)).where(User.username == username)
        )
        return result.scalars().first()

    async def create_user(self, user: User) -> User:
        """Create a new user in the database."""
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def disable_user(self, user_id: int) -> User:
        """Disable a user by setting their status to False."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = False
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def enable_user(self, user_id: int) -> User:
        """Enable a user by setting their status to True."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = True
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def verify_user(self, user_id: int) -> User:
        """Verify a user by setting their is_verified flag to True."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_verified = True
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def get_user_role_name(self, user_id: int) -> str:
        """Fetch the role name of a user by their ID."""
        user = await self.get_user_by_id(user_id)
        if user:
            return user.role.role_name
        return None

    async def get_user_with_citizen_profile(self, user_id: int) -> User:
        """Fetch a user along with their associated citizen profile."""
        result = await self.db.execute(
            select(User).options(selectinload(User.citizen_profile)).where(User.user_id == user_id)
        )
        return result.scalars().first()

    async def get_user_with_employee_profile(self, user_id: int) -> User:
        """Fetch a user along with their associated employee profile."""
        result = await self.db.execute(
            select(User).options(selectinload(User.employee_profile)).where(User.user_id == user_id)
        )
        return result.scalars().first()
