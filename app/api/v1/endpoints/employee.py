"""
Employee API endpoints for managing employee records,
including creation, retrieval, updating, and deletion.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import require_department_admin
from app.api.v1.utils import build_notification_service
from app.core.constants import EMPLOYEE_ACCOUNT_CREATED_EMAIL
from app.db.session import get_db
from app.exceptions.auth_expection import UserAlreadyExistsException
from app.models.employee import Employee
from app.models.roles import Role
from app.models.user import User
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeCreateResponse,
    EmployeeTeamChangeRequest,
)
from app.utils.auth import generate_random_password, get_password_hash

employee_router = APIRouter()


@employee_router.post(
    "/add-staff", response_model=EmployeeCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_employee(
    employee_data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """Create a new employee."""
    try:
        employee_repo = EmployeeRepository(db)
        user_repo = UserRepository(db)
        role_repo = RoleRepository(db)
        citizen_role: Role = await role_repo.get_role_by_name("staff")
        hashed_password = get_password_hash(generate_random_password())
        current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
            user_id=current_user.user_id
        )
        if not current_employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Current user does not have an employee profile.",
            )

        user_department = current_employee.department_id

        existing_user = await user_repo.get_user_by_username(employee_data.email)
        if existing_user:
            raise UserAlreadyExistsException()
        new_user = await user_repo.create_user(
            User(
                username=employee_data.email,
                password_hash=hashed_password,
                role_id=citizen_role.role_id,
                is_verified=True,
                status=True,
            )
        )
        new_employee: Employee | None = await employee_repo.create_employee(
            Employee(
                user_id=new_user.user_id,
                email=employee_data.email,
                phone_number=employee_data.phone_number,
                name=employee_data.name,
                department_id=user_department,
                team_id=employee_data.team_id,
                current_status=employee_data.current_status,
            )
        )
        await build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=None,
            employee_repo=employee_repo,
        ).send_to_user_auto(
            new_user.user_id,
            subject="Employee Account Created",
            body=EMPLOYEE_ACCOUNT_CREATED_EMAIL.format(
                name=employee_data.name, username=employee_data.email
            ),
        )
        return EmployeeCreateResponse(
            message="Employee created successfully.",
            employee_id=new_employee.employee_id,
        )
    except UserAlreadyExistsException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the employee: {str(e)}",
        ) from e


@employee_router.get("/change-team")
async def change_employee_team(
    team_change_request: EmployeeTeamChangeRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_department_admin),
):
    """Change an employee's team."""
    employee_repo = EmployeeRepository(db)
    employee: Employee | None = await employee_repo.get_employee_by_user_id(
        team_change_request.employee_id
    )
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    employee.team_id = team_change_request.new_team_id
    db.commit()
    db.refresh(employee)
    return employee
