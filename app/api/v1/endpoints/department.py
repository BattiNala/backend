"""
Department endpoints for administrative operations. Superadmin-only access is required for department management.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.api.v1.dependencies import get_current_user
from app.repositories.user_repo import UserRepository
from app.repositories.department_repo import DepartmentRepository
from app.schemas.department import DepartmentList, DepartmentCreate

router = APIRouter()

@router.post("/create-department")
async def create_department(
    department_create: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new department when requested by a superadmin user."""
    try:
        user_repo = UserRepository(db)
        user_role_name = await user_repo.get_user_role_name(current_user.user_id)
        if user_role_name != "superadmin":
            raise HTTPException(
                status_code=403, detail="Access forbidden: Superadmin only"
            )

        existing_department = await DepartmentRepository(db).get_department_by_name(department_create.department_name)
        if existing_department:
            raise HTTPException(status_code=400, detail="Department already exists")

        new_department = await DepartmentRepository(db).create_department(department_create.department_name)
        return {"message": f"Department '{new_department.department_name}' created successfully"}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    

@router.get("/list-departments", response_model=DepartmentList)
async def list_departments(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """List all departments."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        departments = await DepartmentRepository(db).list_departments()
        return DepartmentList(departments=departments)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    