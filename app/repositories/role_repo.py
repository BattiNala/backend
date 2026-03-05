from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.roles import Role


class RoleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_role_by_id(self, role_id: int) -> Role:
        result = await self.db.execute(select(Role).where(Role.role_id == role_id))
        return result.scalars().first()

    async def get_role_by_name(self, role_name: str) -> Role:
        result = await self.db.execute(select(Role).where(Role.role_name == role_name))
        return result.scalars().first()

    async def create_role(self, role_name: str) -> Role:
        role = Role(role_name=role_name)
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def list_roles(self) -> list[Role]:
        result = await self.db.execute(select(Role))
        return result.scalars().all()

    async def get_all_user_by_role_id(self, role_id: int) -> list:
        role = await self.get_role_by_id(role_id)
        if role:
            return role.users
        return []
