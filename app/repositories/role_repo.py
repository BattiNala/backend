"""Repository helpers for `Role` entities."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.roles import Role


class RoleRepository:
    """Data-access operations for user roles."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_role_by_id(self, role_id: int) -> Role:
        """Return a role by primary key."""
        result = await self.db.execute(select(Role).where(Role.role_id == role_id))
        return result.scalars().first()

    async def get_role_by_name(self, role_name: str) -> Role:
        """Return a role by unique role name."""
        result = await self.db.execute(select(Role).where(Role.role_name == role_name))
        return result.scalars().first()

    async def create_role(self, role_name: str) -> Role:
        """Create and persist a role."""
        role = Role(role_name=role_name)
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def list_roles(self) -> list[Role]:
        """Return all roles."""
        result = await self.db.execute(select(Role))
        return result.scalars().all()

    async def get_all_user_by_role_id(self, role_id: int) -> list:
        """Return users assigned to a role id."""
        role = await self.get_role_by_id(role_id)
        if role:
            return role.users
        return []
