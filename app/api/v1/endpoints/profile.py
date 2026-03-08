"""Profile related endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_citizen, require_staff
from app.db.session import get_db
from app.models.citizens import Citizen
from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.employee_repo import EmployeeRepository
from app.schemas.citizen import CitizenProfile
from app.schemas.employee import EmployeeProfile

profile_router = APIRouter()


@profile_router.get("/citizen", response_model=CitizenProfile)
async def get_citizen_profile(
    current_citizen: Citizen = Depends(require_citizen),
    db: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated citizen."""
    citizen_repo = CitizenRepository(db)
    citizen_profile: Citizen = await citizen_repo.get_citizen_by_user_id(current_citizen.user_id)
    return CitizenProfile(
        name=citizen_profile.name,
        email=citizen_profile.email,
        phone_number=citizen_profile.phone_number,
        address=citizen_profile.home_address,
        trust_score=citizen_profile.trust_score,
    )


@profile_router.get("/employee", response_model=EmployeeProfile)
async def get_employee_profile(
    current_employee: Employee = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated employee."""
    employee_repo = EmployeeRepository(db)
    _employee_profile: Employee = await employee_repo.get_employee_profile_by_user_id(
        current_employee.user_id
    )
    team: Team = _employee_profile.teams
    department: Department = team.department if team else None

    return EmployeeProfile(
        name=_employee_profile.name,
        email=_employee_profile.email,
        phone_number=_employee_profile.phone_number,
        team_name=team.team_name if team else None,
        department_name=department.department_name if department else None,
    )
