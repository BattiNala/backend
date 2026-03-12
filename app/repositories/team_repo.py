"""
Team repository for handling database operations related to teams.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team
from app.schemas.team import TeamCreate, TeamDetail, TeamUpdate


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

    async def update_team(self, team_update: TeamUpdate) -> Team | None:
        """Update an existing team."""
        team = await self.db.get(Team, team_update.team_id)
        if not team:
            return None

        team.team_name = (
            team_update.team_name if team_update.team_name is not None else team.team_name
        )
        team.base_latitude = (
            team_update.base_latitude
            if team_update.base_latitude is not None
            else team.base_latitude
        )
        team.base_longitude = (
            team_update.base_longitude
            if team_update.base_longitude is not None
            else team.base_longitude
        )
        team.coverage_radius_km = (
            team_update.coverage_radius_km
            if team_update.coverage_radius_km is not None
            else team.coverage_radius_km
        )
        team.status = team_update.status if team_update.status is not None else team.status
        self.db.add(team)
        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def update_team_status(self, team_id: int, status: bool) -> Team | None:
        """Update the availability status of a team."""
        team = await self.db.get(Team, team_id)
        if not team:
            return None

        team.status = status
        self.db.add(team)
        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def get_team_by_id(self, team_id: int) -> Team | None:
        """Get a team by its ID."""
        return await self.db.get(Team, team_id)

    async def list_teams(self):
        """List all teams."""
        result = await self.db.execute(select(Team))
        return result.scalars().all()

    async def list_teams_by_department(self, department_id: int):
        """
        List all teams belonging to a specific department with department name.
        """

        result = await self.db.execute(
            select(Team)
            .options(selectinload(Team.department))
            .where(Team.department_id == department_id)
        )

        teams = result.scalars().all()

        return [
            TeamDetail(
                team_id=team.team_id,
                team_name=team.team_name,
                department_id=team.department_id,
                base_latitude=float(team.base_latitude),
                base_longitude=float(team.base_longitude),
                coverage_radius_km=team.coverage_radius_km,
                status=team.status,
                department_name=team.department.department_name,
            )
            for team in teams
        ]
