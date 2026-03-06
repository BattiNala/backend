from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: int) -> User:
        result = await self.db.execute(
            select(User).options(selectinload(User.role)).where(User.user_id == user_id)
        )
        return result.scalars().first()

    async def get_user_by_username(self, username: str) -> User:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.username == username)
        )
        return result.scalars().first()

    async def create_user(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def disable_user(self, user_id: int) -> User:
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = False
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def enable_user(self, user_id: int) -> User:
        user = await self.get_user_by_id(user_id)
        if user:
            user.status = True
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def verify_user(self, user_id: int) -> User:
        user = await self.get_user_by_id(user_id)
        if user:
            user.is_verified = True
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def get_user_role_name(self, user_id: int) -> str:
        user = await self.get_user_by_id(user_id)
        if user:
            return user.role.role_name
        return None

    async def get_user_with_citizen_profile(self, user_id: int) -> User:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.citizen_profile))
            .where(User.user_id == user_id)
        )
        return result.scalars().first()
