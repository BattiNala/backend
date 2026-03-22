"""
Department endpoints for administrative operations.
Superadmin-only access is required for department management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_superadmin
from app.api.v1.utils import with_db_error
from app.db.session import get_db
from app.models.department import Department
from app.models.employee import Employee
from app.models.roles import Role
from app.models.user import User
from app.repositories.department_repo import DepartmentRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.department import (
    DepartmentAdmin,
    DepartmentAdminCreate,
    DepartmentCreate,
    DepartmentList,
)
from app.utils.auth import get_password_hash

department_router = APIRouter()


@department_router.post(
    "/create-department",
    dependencies=[Depends(require_superadmin)],
    summary="Create a new department",
    description="Create a new department (superadmin only).",
)
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

        new_department: Department = await DepartmentRepository(db).create_department(
            department_create.department_name
        )
        return {"message": f"Department '{new_department.department_name}' created successfully"}

    return await with_db_error(_create)


@department_router.get(
    "/list-departments",
    response_model=DepartmentList,
    dependencies=[Depends(get_current_user)],
    summary="List all departments",
    description="List all departments (accessible to all authenticated users).",
)
async def list_departments(
    db: AsyncSession = Depends(get_db),
):
    """List all departments."""

    async def _list() -> DepartmentList:
        departments = await DepartmentRepository(db).list_departments()
        return DepartmentList(departments=departments)

    return await with_db_error(_list)


@department_router.post(
    "/add-department-admin",
    dependencies=[Depends(require_superadmin)],
    summary="Add a department admin to a department",
    description="Add a department admin to a department (superadmin only).",
    status_code=status.HTTP_201_CREATED,
)
async def add_department_admin(
    department_admin_create: DepartmentAdminCreate, db: AsyncSession = Depends(get_db)
):
    """Add a department admin to a department (superadmin only)."""
    try:
        role_repo = RoleRepository(db)
        department_admin_role: Role = await role_repo.get_role_by_name("department_admin")
        if not department_admin_role:
            raise HTTPException(status_code=500, detail="Department admin role not found")

        user_repo = UserRepository(db)
        # Check if user already exists with the given email
        existing_user = await user_repo.get_user_by_username(department_admin_create.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        password_hash = get_password_hash(department_admin_create.password)
        new_user: User = await user_repo.create_user(
            User(
                username=department_admin_create.email,
                password_hash=password_hash,
                role_id=department_admin_role.role_id,
                status=True,
                is_verified=True,
            )
        )

        employee_repo = EmployeeRepository(db)
        new_department_admin: Employee = await employee_repo.create_employee(
            Employee(
                name=department_admin_create.name,
                email=department_admin_create.email,
                phone_number=department_admin_create.phone_number,
                user_id=new_user.user_id,
                department_id=department_admin_create.department_id,
                team_id=None,
            )
        )
        department_repo = DepartmentRepository(db)
        department: Department = await department_repo.get_department_by_id(
            department_admin_create.department_id
        )
        await db.commit()
        return {
            "message": (
                f"Department admin '{new_department_admin.name}' created successfully for "
                f"department '{department.department_name}'"
            )
        }

    except Exception as e:
        await db.rollback()
        print(f"Error creating department admin: {e}")
        raise HTTPException(status_code=500, detail="Failed to create department admin") from e


@department_router.get(
    "/list-department-admins",
    response_model=list[DepartmentAdmin],
    dependencies=[Depends(require_superadmin)],
    summary="List department admins",
    description="List all department admins, optionally filtered by department (superadmin only).",
)
async def list_department_admins(
    department_id: int | None = None, db: AsyncSession = Depends(get_db)
) -> list[DepartmentAdmin]:
    """List department admins, optionally filtered by department."""
    department_repo = DepartmentRepository(db)
    return await department_repo.list_department_admins(department_id)
