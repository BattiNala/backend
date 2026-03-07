"""
Department endpoints for administrative operations.
Superadmin-only access is required for department management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_superadmin
from app.api.v1.utils import with_db_error
from app.db.session import get_db
from app.repositories.department_repo import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentList

department_router = APIRouter()


@department_router.post("/create-department", dependencies=[Depends(require_superadmin)])
async def create_department(
    department_create: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new department when requested by a superadmin user."""
    async def _create() -> dict:
        existing_department = await DepartmentRepository(db).get_department_by_name(
            department_create.department_name
        )
        if existing_department:
            raise HTTPException(status_code=400, detail="Department already exists")

        new_department = await DepartmentRepository(db).create_department(
            department_create.department_name
        )
        return {"message": f"Department '{new_department.department_name}' created successfully"}

    return await with_db_error(_create)


@department_router.get(
    "/list-departments",
    response_model=DepartmentList,
    dependencies=[Depends(get_current_user)],
)
async def list_departments(
    db: AsyncSession = Depends(get_db),
):
    """List all departments."""
    async def _list() -> DepartmentList:
        departments = await DepartmentRepository(db).list_departments()
        return DepartmentList(departments=departments)

    return await with_db_error(_list)
