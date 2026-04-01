"""
Role-Based Access Control (RBAC) utilities for the application.
"""

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.user_repo import UserRepository
from app.schemas.issue import IssueListFilters, IssuePriority, IssueStatus


@dataclass(slots=True)
class IssueEndpointContext:
    """Request-scoped dependencies shared by issue endpoints."""

    db: AsyncSession
    current_user: User


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


def get_issue_list_filters(
    issue_status: IssueStatus | None = None,
    priority: IssuePriority | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> IssueListFilters:
    """Build list filters from query params."""
    return IssueListFilters(
        status=issue_status,
        priority=priority,
        date_from=date_from,
        date_to=date_to,
    )


async def scope_issue_filters_for_user(
    context: IssueEndpointContext, filters: IssueListFilters
) -> IssueListFilters:
    """Apply role-based issue visibility filters for the current user."""
    user_repo = UserRepository(context.db)
    role_name = await user_repo.get_user_role_name(context.current_user.user_id)

    if role_name == "superadmin":
        return filters

    if role_name in {"department_admin", "staff"}:
        employee_repo = EmployeeRepository(context.db)
        employee = await employee_repo.get_employee_by_user_id(context.current_user.user_id)
        if not employee:
            raise HTTPException(status_code=403, detail="Access forbidden.")
        if role_name == "department_admin":
            filters.department_id = employee.department_id
        else:
            filters.assignee_id = employee.employee_id
        return filters

    if role_name == "citizen":
        citizen_repo = CitizenRepository(context.db)
        citizen = await citizen_repo.get_citizen_by_user_id(context.current_user.user_id)
        if not citizen:
            raise HTTPException(status_code=403, detail="Access forbidden.")
        filters.reporter_id = citizen.citizen_id
        return filters

    raise HTTPException(status_code=403, detail="Access forbidden.")
