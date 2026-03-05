# repo for citizen related database operations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.citizens import Citizen


class CitizenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_citizen_by_id(self, citizen_id: int) -> Citizen:
        result = await self.db.execute(
            select(Citizen)
            .options(selectinload(Citizen.user))
            .where(Citizen.citizen_id == citizen_id)
        )
        return result.scalars().first()

    async def create_citizen(self, citizen: Citizen) -> Citizen:
        self.db.add(citizen)
        await self.db.commit()
        await self.db.refresh(citizen)
        return citizen
