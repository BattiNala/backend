"""
Role-Based Access Control (RBAC) utilities for the application.
"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.employee_repo import EmployeeRepository


async def authorize_issue_access(issue, current_user: User | None, db: AsyncSession) -> None:
    """Validate whether the current user can access the issue."""
    if issue.is_anonymous:
        return

    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    role_name = current_user.role.role_name

    if role_name == "department_admin":
        await authorize_department_admin(issue, current_user, db)
    elif role_name == "staff":
        await authorize_staff(issue, current_user, db)
    elif role_name == "citizen":
        await authorize_citizen(issue, current_user, db)


async def authorize_department_admin(issue, current_user: User, db: AsyncSession) -> None:
    """Ensure the current user is a department admin of the issue's department."""
    employee_repo = EmployeeRepository(db)
    employee = await employee_repo.get_employee_by_user_id(current_user.user_id)

    if not employee or issue.issue_type != employee.department_id:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Wrong department.",
        )


async def authorize_staff(issue, current_user: User, db: AsyncSession) -> None:
    """Ensure the current user is the assignee of the issue."""
    employee_repo = EmployeeRepository(db)
    employee = await employee_repo.get_employee_by_user_id(current_user.user_id)

    if not employee:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Employee record not found.",
        )

    if issue.assignee_id != employee.employee_id:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Not assignee.",
        )


async def authorize_citizen(issue, current_user: User, db: AsyncSession) -> None:
    """Ensure the current user is the reporter of the issue."""
    citizen_repo = CitizenRepository(db)
    citizen = await citizen_repo.get_citizen_by_user_id(current_user.user_id)

    if not citizen or issue.reporter_id != citizen.citizen_id:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Not reporter.",
        )
