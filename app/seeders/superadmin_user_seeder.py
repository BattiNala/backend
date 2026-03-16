# pylint: disable=missing-module-docstring

import asyncio

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.seeders.superadmin_role_seeder import seed_superadmin_role

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


async def seed_superadmin_user(db: AsyncSession):
    """Seed the database with a superadmin user if it doesn't already exist."""
    await seed_superadmin_role(db)
    superadmin_role = await RoleRepository(db).get_role_by_name("superadmin")
    superadmin_role_id = superadmin_role.role_id if superadmin_role else None

    user_repo = UserRepository(db)
    superadmin_user = await user_repo.get_user_by_username("superadmin")
    hashed_password = pwd_context.hash("superadminpassword")
    if not superadmin_user:
        new_user = User(
            username="superadmin",
            password_hash=hashed_password,
            role_id=superadmin_role_id,
            status=True,
            is_verified=True,
        )
        await user_repo.create_user(new_user)
        print("Superadmin user created.")
    else:
        print("Superadmin user already exists.")


async def main():
    """Run the superadmin seeding flow with an application session."""
    async with AsyncSessionLocal() as session:
        await seed_superadmin_user(session)


if __name__ == "__main__":
    asyncio.run(main())
