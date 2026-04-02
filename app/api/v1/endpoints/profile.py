"""Profile related endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_citizen, require_staff
from app.db.session import get_db
from app.models.citizens import Citizen
from app.models.employee import Employee
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.employee_repo import EmployeeRepository
from app.schemas.citizen import CitizenProfile
from app.schemas.employee import EmployeeProfile
from app.utils.return_wrappers.profile import wrap_citizen_profile, wrap_employee_profile

profile_router = APIRouter()


@profile_router.get("/citizen", response_model=CitizenProfile)
async def get_citizen_profile(
    current_citizen: Citizen = Depends(require_citizen),
    db: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated citizen."""
    citizen_repo = CitizenRepository(db)
    citizen: Citizen = await citizen_repo.get_citizen_by_user_id(current_citizen.user_id)
    return wrap_citizen_profile(citizen)


@profile_router.get("/employee", response_model=EmployeeProfile)
async def get_employee_profile(
    current_employee: Employee = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """Return the profile of the currently authenticated employee."""
    employee_repo = EmployeeRepository(db)
    emp: Employee = await employee_repo.get_employee_profile_by_user_id(current_employee.user_id)
    return wrap_employee_profile(employee=emp)
