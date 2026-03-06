"""Repository helpers for `Citizen` persistence and lookup."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.citizens import Citizen


class CitizenRepository:
    """Data-access operations for citizen records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_citizen_by_id(self, citizen_id: int) -> Citizen:
        """Return a citizen by primary key with linked user loaded."""
        result = await self.db.execute(
            select(Citizen)
            .options(selectinload(Citizen.user))
            .where(Citizen.citizen_id == citizen_id)
        )
        return result.scalars().first()

    async def get_citizen_by_user_id(self, user_id: int) -> Citizen:
        """Return a citizen profile by associated user id."""
        result = await self.db.execute(
            select(Citizen)
            .options(selectinload(Citizen.user))
            .where(Citizen.user_id == user_id)
        )
        return result.scalars().first()

    async def create_citizen(self, citizen: Citizen) -> Citizen:
        """Persist a new citizen record and return the refreshed entity."""
        self.db.add(citizen)
        await self.db.commit()
        await self.db.refresh(citizen)
        return citizen
