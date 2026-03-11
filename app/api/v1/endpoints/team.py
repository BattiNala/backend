"""
Team endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_department_admin
from app.db.session import get_db
from app.models.user import User
from app.repositories.team_repo import TeamRepository
from app.repositories.user_repo import UserRepository
from app.schemas.team import Team, TeamCreate

team_router = APIRouter()


@team_router.get("/teams")
async def get_teams():
    """
    Get all teams.
    """
    # Placeholder implementation, replace with actual database query
    return {"message": "List of teams will be returned here."}


@team_router.get("/teams/{team_id}")
async def get_team(team_id: int):
    """
    Get a team by ID.
    """
    # Placeholder implementation, replace with actual database query
    return {"message": f"Details of team with ID {team_id} will be returned here."}


@team_router.post("/create-team", dependencies=[Depends(require_department_admin)])
async def create_team(
    team: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """
    Create a new team.
    """
    user_repository = UserRepository(db)
    user_with_profile = await user_repository.get_user_with_employee_profile(
        user_id=current_user.user_id
    )
    employee_profile = user_with_profile.employee_profile if user_with_profile else None
    if not employee_profile:
        return {"error": "Current user does not have an employee profile."}
    user_department = employee_profile.department_id
    if not user_department:
        return {"error": "Current user's employee profile is not associated with any department."}

    team_repository = TeamRepository(db)
    new_team: Team = await team_repository.create_team(team_create=team, dep_id=user_department)
    return {
        "message": "Team created successfully. {team_name} is now available to handle issues"
        " in department {department_id}.".format(
            team_name=new_team.team_name, department_id=user_department
        ),
    }
