"""
Team endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_department_admin
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.team_repo import TeamRepository
from app.schemas.team import Team, TeamCreate, TeamList

team_router = APIRouter()


@team_router.get(
    "/list-teams",
    dependencies=[Depends(require_department_admin)],
    response_model=TeamList,
    summary="List Teams of My Department",
    description="Get all teams of my department.",
    responses={
        403: {
            "description": "Access forbidden: Department Admin or Superadmin only",
            "content": {"application/json": {"example": {"detail": "Not enough permissions"}}},
        },
        404: {
            "description": "Current user doesn't have an employee profile "
            "or is not associated with any department",
            "content": {
                "application/json": {
                    "example": {"detail": "Current user does not have an employee profile."}
                }
            },
        },
    },
)
async def get_teams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """
    Get all teams of my department.
    """
    employee_repo = EmployeeRepository(db)
    employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=current_user.user_id
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user does not have an employee profile.",
        )

    user_department = employee.department_id

    if not user_department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user's employee profile is not associated with any department.",
        )
    team_repository = TeamRepository(db)
    teams = await team_repository.list_teams_by_department(department_id=user_department)
    return TeamList(teams=teams)


@team_router.get(
    "/teams/{team_id}",
    response_model=Team,
    dependencies=[Depends(require_department_admin)],
    responses={
        403: {
            "description": "Access forbidden: Department Admin or Superadmin only",
            "content": {"application/json": {"example": {"detail": "Not enough permissions"}}},
        },
        404: {
            "description": "Team not found or current user doesn't have access to the team",
            "content": {"application/json": {"example": {"detail": "Team not found."}}},
        },
    },
)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """
    Get a team by ID.
    """
    employee_repo = EmployeeRepository(db)
    employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=current_user.user_id
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user does not have an employee profile.",
        )
    user_department = employee.department_id
    if not user_department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user's employee profile is not associated with any department.",
        )

    team_repository = TeamRepository(db)
    team: Team | None = await team_repository.get_team_by_id(team_id=team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found.",
        )
    if team.department_id != user_department:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this team.",
        )
    return team


@team_router.post(
    "/create-team",
    dependencies=[Depends(require_department_admin)],
    status_code=status.HTTP_201_CREATED,
    summary="Create a New Team",
    description="Create a new team for current user's department(Requires department admin)",
    response_model=dict,
    responses={
        403: {
            "description": "Access forbidden: Department Admin or Superadmin only",
            "content": {"application/json": {"example": {"detail": "Not enough permissions"}}},
        },
        404: {
            "description": "Current user doesn't have an employee profile"
            " or is not associated with any department",
            "content": {
                "application/json": {
                    "example": {"detail": "Current user does not have an employee profile."}
                }
            },
        },
    },
)
async def create_team(
    team: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """
    Create a new team.
    """
    employee_repo = EmployeeRepository(db)
    employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=current_user.user_id
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user does not have an employee profile.",
        )

    user_department = employee.department_id
    if not user_department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user's employee profile is not associated with any department.",
        )

    team_repository = TeamRepository(db)
    new_team: Team = await team_repository.create_team(team_create=team, dep_id=user_department)
    return {
        "message": (
            f"Team created successfully. {new_team.team_name} is now available to handle "
            f"issues in department {user_department}."
        )
    }
