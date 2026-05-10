"""Superadmin-only endpoints for administrative operations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_superadmin
from app.db.session import get_db
from app.repositories.employee_repo import EmployeeRepository
from app.schemas.employee import EmployeeProfile
from app.utils.return_wrappers.profile import wrap_employee_profile

superadmin_router = APIRouter()


@superadmin_router.get("/superadmin-only", dependencies=[Depends(require_superadmin)])
async def superadmin_only():
    """Allow access only to users with the superadmin role."""
    return {"message": "Welcome, Superadmin!"}


@superadmin_router.get(
    "/all-employees",
    response_model=list[EmployeeProfile],
    dependencies=[Depends(require_superadmin)],
    summary="List all employees",
    description="List all employees across all departments (superadmin only).",
)
async def list_all_employees(
    db: AsyncSession = Depends(get_db),
) -> list[EmployeeProfile]:
    """List all employees in the system (superadmin only)."""
    employee_repo = EmployeeRepository(db)
    result = await employee_repo.get_all_employees()
    return [wrap_employee_profile(employee) for employee in result]
