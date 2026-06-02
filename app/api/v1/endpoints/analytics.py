"""Analytics endpoints for dashboard and reporting."""
# pylint: disable=not-callable

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_department_admin, require_superadmin
from app.db.session import get_db
from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team
from app.models.user import User
from app.repositories.analytics_repo import AnalyticsRepository
from app.repositories.employee_repo import EmployeeRepository
from app.schemas.analytics import (
    DashboardSummaryResponse,
    DepartmentAnalyticsResponse,
    EmployeeAnalyticsResponse,
    IssueStatsResponse,
    IssueTrendResponse,
    TeamAnalyticsResponse,
    TopPerformingEmployeesResponse,
    TopPerformingTeamsResponse,
    UserStatsResponse,
)

analytics_router = APIRouter()


@analytics_router.get(
    "/issues/stats",
    response_model=IssueStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Issue Statistics",
    description="Retrieve overall issue statistics with optional filters.",
)
async def get_issue_stats(
    date_from: str | None = Query(None, description="Start date (ISO format)"),
    date_to: str | None = Query(None, description="End date (ISO format)"),
    department_id: int | None = Query(None, description="Filter by department ID"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_department_admin),
):
    """Get overall issue statistics."""
    parsed_date_from = datetime.fromisoformat(date_from) if date_from else None
    parsed_date_to = datetime.fromisoformat(date_to) if date_to else None
    employee_repo = EmployeeRepository(db)
    current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=_current_user.user_id
    )
    if current_employee and not department_id:
        department_id = current_employee.department_id

    repo = AnalyticsRepository(db)
    stats = await repo.get_issue_statistics(
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        department_id=department_id,
    )
    return IssueStatsResponse(**stats)


@analytics_router.get(
    "/departments",
    response_model=DepartmentAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Department Analytics",
    description="Retrieve issue statistics per department.",
)
async def get_department_analytics(
    date_from: str | None = Query(None, description="Start date (ISO format)"),
    date_to: str | None = Query(None, description="End date (ISO format)"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_department_admin),
):
    """Get department-wise analytics."""
    parsed_date_from = datetime.fromisoformat(date_from) if date_from else None
    parsed_date_to = datetime.fromisoformat(date_to) if date_to else None

    repo = AnalyticsRepository(db)
    departments = await repo.get_department_analytics(
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )
    return DepartmentAnalyticsResponse(
        departments=departments,
        total_departments=len(departments),
    )


@analytics_router.get(
    "/employees",
    response_model=EmployeeAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Employee Analytics",
    description="Retrieve performance statistics per employee.",
)
async def get_employee_analytics(
    department_id: int | None = Query(None, description="Filter by department ID"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_department_admin),
):
    """Get employee performance analytics."""
    repo = AnalyticsRepository(db)
    employee_repo = EmployeeRepository(db)
    current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=_current_user.user_id
    )
    if current_employee and not department_id:
        department_id = current_employee.department_id
    employees = await repo.get_employee_analytics(department_id=department_id)

    avg_resolution_rate = 0.0
    if employees:
        avg_resolution_rate = round(
            sum(e["resolution_rate"] for e in employees) / len(employees), 2
        )

    return EmployeeAnalyticsResponse(
        employees=employees,
        total_employees=len(employees),
        avg_resolution_rate=avg_resolution_rate,
    )


@analytics_router.get(
    "/issues/trend",
    response_model=IssueTrendResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Issue Trend",
    description="Retrieve daily issue trend over time.",
)
async def get_issue_trend(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    department_id: int | None = Query(None, description="Filter by department ID"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_department_admin),
):
    """Get issue trend over time."""
    employee_repo = EmployeeRepository(db)
    current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=_current_user.user_id
    )
    if current_employee and not department_id:
        department_id = current_employee.department_id
    repo = AnalyticsRepository(db)
    trend = await repo.get_issue_trend(days=days, department_id=department_id)
    return IssueTrendResponse(trend=trend, total_days=len(trend))


@analytics_router.get(
    "/users",
    response_model=UserStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User Statistics",
    description="Retrieve overall user statistics and role distribution.",
)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_superadmin),
):
    """Get user statistics."""

    repo = AnalyticsRepository(db)
    stats = await repo.get_user_statistics()
    return UserStatsResponse(**stats)


@analytics_router.get(
    "/teams",
    response_model=TeamAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Team Analytics",
    description="Retrieve workload statistics per team.",
)
async def get_team_analytics(
    department_id: int | None = Query(None, description="Filter by department ID"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_department_admin),
):
    """Get team workload analytics."""

    repo = AnalyticsRepository(db)
    employee_repo = EmployeeRepository(db)
    current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=_current_user.user_id
    )
    if current_employee and not department_id:
        department_id = current_employee.department_id
    teams = await repo.get_team_analytics(department_id=department_id)
    return TeamAnalyticsResponse(teams=teams, total_teams=len(teams))


@analytics_router.get(
    "/employees/top",
    response_model=TopPerformingEmployeesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Top Performing Employees",
    description="Retrieve top performing employees by resolution rate.",
)
async def get_top_employees(
    limit: int = Query(10, ge=1, le=50, description="Number of top employees"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """Get top performing employees."""
    employee_repo = EmployeeRepository(db)
    current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=current_user.user_id
    )
    repo = AnalyticsRepository(db)
    if current_employee:
        user_department = current_employee.department_id
        employees = await repo.get_top_employees(limit=limit, department_id=user_department)
    else:
        employees = await repo.get_top_employees(limit=limit)
    return TopPerformingEmployeesResponse(employees=employees)


@analytics_router.get(
    "/teams/top",
    response_model=TopPerformingTeamsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Top Performing Teams",
    description="Retrieve top performing teams by resolution rate.",
)
async def get_top_teams(
    limit: int = Query(10, ge=1, le=50, description="Number of top teams"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """Get top performing teams."""
    employee_repo = EmployeeRepository(db)
    current_employee: Employee | None = await employee_repo.get_employee_by_user_id(
        user_id=current_user.user_id
    )
    repo = AnalyticsRepository(db)
    if current_employee:
        user_department = current_employee.department_id
        teams = await repo.get_top_teams(limit=limit, department_id=user_department)
    else:
        teams = await repo.get_top_teams(limit=limit)
    return TopPerformingTeamsResponse(teams=teams)


@analytics_router.get(
    "/dashboard",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Dashboard Summary",
    description="Retrieve comprehensive dashboard summary with all key metrics.",
)
async def get_dashboard_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days for trend"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_superadmin),
):
    """Get comprehensive dashboard summary."""
    repo = AnalyticsRepository(db)

    issue_stats = await repo.get_issue_statistics()
    user_stats = await repo.get_user_statistics()
    trend = await repo.get_issue_trend(days=days)

    dept_result = await db.execute(select(func.count()).select_from(Department))
    total_departments = dept_result.scalar() or 0

    team_result = await db.execute(select(func.count()).select_from(Team))
    total_teams = team_result.scalar() or 0

    return DashboardSummaryResponse(
        issue_stats=IssueStatsResponse(**issue_stats),
        user_stats=UserStatsResponse(**user_stats),
        total_departments=total_departments,
        total_teams=total_teams,
        recent_issue_trend=trend,
    )
