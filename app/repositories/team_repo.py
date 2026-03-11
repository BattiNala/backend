"""
Team repository for handling database operations related to teams.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # noqa: F401

from app.models.team import Team
from app.schemas.team import TeamCreate


class TeamRepository:
    """Repository for managing team-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_team(self, team_create: TeamCreate, dep_id: int) -> Team:
        """Create a new team."""
        new_team = Team(
            team_name=team_create.team_name,
            department_id=dep_id,
            base_latitude=team_create.base_latitude,
            base_longitude=team_create.base_longitude,
            coverage_radius_km=team_create.coverage_radius_km,
        )
        self.db.add(new_team)
        await self.db.commit()
        await self.db.refresh(new_team)
        return new_team

    async def get_team_by_id(self, team_id: int):
        """Get a team by its ID."""
        return await self.db.get(Team, team_id)

    async def get_team_by_name(self, team_name: str):
        """Get a team by its name."""
        result = await self.db.execute(select(Team).where(Team.team_name == team_name))
        return result.scalars().first()

    async def list_teams(self):
        """List all teams."""
        result = await self.db.execute(select(Team))
        return result.scalars().all()
