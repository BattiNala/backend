from sqlalchemy.ext.asyncio import AsyncSession
from app.models.roles import Role
from app.repositories.role_repo import RoleRepository


async def seed_superadmin_role(db: AsyncSession):
    role_repo = RoleRepository(db)
    superadmin_role = await role_repo.get_role_by_name("superadmin")
    if not superadmin_role:
        new_role = Role(role_name="superadmin")
        await role_repo.create_role(new_role)
        print("Superadmin role created.")
    else:
        print("Superadmin role already exists.")
