"""Analytics repository for dashboard and reporting queries."""
# pylint: disable=not-callable

from datetime import datetime, timedelta

from sqlalchemy import Date, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.citizens import Citizen
from app.models.department import Department
from app.models.employee import Employee
from app.models.issue import Issue
from app.models.roles import Role
from app.models.team import Team
from app.models.user import User
from app.schemas.employee import EmployeeActivityStatus
from app.schemas.issue import IssueStatus


class AnalyticsRepository:
    """Repository for analytics and reporting queries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_issue_statistics(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        department_id: int | None = None,
    ) -> dict:
        """Get overall issue statistics with optional filters."""
        base_filters = []
        if date_from:
            base_filters.append(Issue.created_at >= date_from)
        if date_to:
            base_filters.append(Issue.created_at <= date_to)
        if department_id is not None:
            base_filters.append(Issue.issue_type == department_id)

        total_issues = await self._count_issues(base_filters)

        status_counts = {}
        for status in IssueStatus:
            status_filters = base_filters + [Issue.status == status]
            status_counts[status.value] = await self._count_issues(status_filters)

        priority_counts = {}
        priority_breakdown = []
        for priority in ["LOW", "NORMAL", "HIGH"]:
            priority_filters = base_filters + [Issue.issue_priority == priority]
            count = await self._count_issues(priority_filters)
            priority_counts[priority] = count
            if count > 0:
                priority_breakdown.append({"priority": priority, "count": count})

        status_breakdown = []
        for status in IssueStatus:
            count = status_counts[status.value]
            if count > 0:
                status_breakdown.append({"status": status.value, "count": count})

        return {
            "total_issues": total_issues,
            "open_issues": status_counts.get(IssueStatus.OPEN.value, 0),
            "in_progress_issues": status_counts.get(IssueStatus.IN_PROGRESS.value, 0),
            "resolved_issues": status_counts.get(IssueStatus.RESOLVED.value, 0),
            "rejected_issues": status_counts.get(IssueStatus.REJECTED.value, 0),
            "pending_verification_issues": status_counts.get(
                IssueStatus.PENDING_VERIFICATION.value, 0
            ),
            "status_breakdown": status_breakdown,
            "priority_breakdown": priority_breakdown,
        }

    async def get_department_analytics(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Get issue statistics per department."""
        stmt = (
            select(
                Department.department_id,
                Department.department_name,
                func.count(Issue.issue_id).label("total_issues"),
                func.sum(case((Issue.status == IssueStatus.OPEN, 1), else_=0)).label("open_issues"),
                func.sum(case((Issue.status == IssueStatus.RESOLVED, 1), else_=0)).label(
                    "resolved_issues"
                ),
            )
            .outerjoin(Issue, Issue.issue_type == Department.department_id)
            .group_by(Department.department_id, Department.department_name)
        )

        if date_from:
            stmt = stmt.where(Issue.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Issue.created_at <= date_to)

        result = await self.db.execute(stmt)
        rows = result.all()

        departments = []
        for row in rows:
            departments.append(
                {
                    "department_id": row.department_id,
                    "department_name": row.department_name,
                    "total_issues": row.total_issues or 0,
                    "open_issues": row.open_issues or 0,
                    "resolved_issues": row.resolved_issues or 0,
                    "avg_resolution_time_hours": None,
                }
            )

        return departments

    async def get_employee_analytics(
        self,
        department_id: int | None = None,
    ) -> list[dict]:
        """Get performance statistics per employee."""
        stmt = (
            select(
                Employee.employee_id,
                Employee.name,
                Department.department_name,
                func.count(Issue.issue_id).label("total_assigned"),
                func.sum(case((Issue.status == IssueStatus.RESOLVED, 1), else_=0)).label(
                    "resolved_count"
                ),
                func.sum(case((Issue.status == IssueStatus.IN_PROGRESS, 1), else_=0)).label(
                    "in_progress_count"
                ),
            )
            .join(Department, Employee.department_id == Department.department_id)
            .outerjoin(Issue, Issue.assignee_id == Employee.employee_id)
            .group_by(
                Employee.employee_id,
                Employee.name,
                Department.department_name,
            )
        )

        if department_id is not None:
            stmt = stmt.where(Employee.department_id == department_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        employees = []
        for row in rows:
            total = row.total_assigned or 0
            resolved = row.resolved_count or 0
            resolution_rate = (resolved / total) if total > 0 else 0.0

            employees.append(
                {
                    "employee_id": row.employee_id,
                    "name": row.name,
                    "department_name": row.department_name,
                    "total_assigned": total,
                    "resolved_count": resolved,
                    "in_progress_count": row.in_progress_count or 0,
                    "resolution_rate": round(resolution_rate, 2),
                }
            )

        return employees

    async def get_issue_trend(
        self,
        days: int = 30,
        department_id: int | None = None,
    ) -> list[dict]:
        """Get daily issue trend for the specified number of days."""
        date_from = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(
                func.cast(Issue.created_at, Date).label("date"),
                func.count(Issue.issue_id).label("count"),
            )
            .where(Issue.created_at >= date_from)
            .group_by(func.cast(Issue.created_at, Date))
            .order_by(func.cast(Issue.created_at, Date))
        )

        if department_id is not None:
            stmt = stmt.where(Issue.issue_type == department_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        trend = []
        for row in rows:
            trend.append({"date": str(row.date), "count": row.count})

        return trend

    async def get_user_statistics(self) -> dict:
        """Get overall user statistics."""
        total_users = await self._count_users()
        total_citizens = await self._count_citizens()
        total_employees = await self._count_employees()

        role_stmt = (
            select(Role.role_name, func.count(User.user_id).label("count"))
            .join(User, User.role_id == Role.role_id)
            .group_by(Role.role_name)
        )
        role_result = await self.db.execute(role_stmt)
        role_rows = role_result.all()

        role_distribution = [{"role_name": row.role_name, "count": row.count} for row in role_rows]

        return {
            "total_users": total_users,
            "total_citizens": total_citizens,
            "total_employees": total_employees,
            "role_distribution": role_distribution,
        }

    async def get_team_analytics(
        self,
        department_id: int | None = None,
    ) -> list[dict]:
        """Get workload statistics per team."""
        stmt = (
            select(
                Team.team_id,
                Team.team_name,
                Department.department_name,
                func.count(Employee.employee_id).label("total_members"),
                func.sum(
                    case(
                        (Employee.current_status == EmployeeActivityStatus.AVAILABLE, 1),
                        else_=0,
                    )
                ).label("available_members"),
                func.sum(
                    case(
                        (Employee.current_status == EmployeeActivityStatus.BUSY, 1),
                        else_=0,
                    )
                ).label("busy_members"),
            )
            .join(Department, Team.department_id == Department.department_id)
            .outerjoin(Employee, Employee.team_id == Team.team_id)
            .group_by(
                Team.team_id,
                Team.team_name,
                Department.department_name,
            )
        )

        if department_id is not None:
            stmt = stmt.where(Team.department_id == department_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        teams = []
        for row in rows:
            stmt_issues = (
                select(func.count(Issue.issue_id))
                .join(Employee, Issue.assignee_id == Employee.employee_id)
                .where(Employee.team_id == row.team_id)
            )
            issue_result = await self.db.execute(stmt_issues)
            assigned_issues = issue_result.scalar() or 0

            teams.append(
                {
                    "team_id": row.team_id,
                    "team_name": row.team_name,
                    "department_name": row.department_name,
                    "total_members": row.total_members or 0,
                    "available_members": row.available_members or 0,
                    "busy_members": row.busy_members or 0,
                    "assigned_issues": assigned_issues,
                }
            )

        return teams

    async def get_top_employees(self, limit: int = 10) -> list[dict]:
        """Get top performing employees by resolution rate."""
        employees = await self.get_employee_analytics()
        employees.sort(key=lambda e: e["resolution_rate"], reverse=True)
        return employees[:limit]

    async def get_top_teams(self, limit: int = 10) -> list[dict]:
        """Get top performing teams by resolved issues."""
        teams = await self.get_team_analytics()

        for team in teams:
            stmt = (
                select(func.count(Issue.issue_id))
                .join(Employee, Issue.assignee_id == Employee.employee_id)
                .where(
                    Employee.team_id == team["team_id"],
                    Issue.status == IssueStatus.RESOLVED,
                )
            )
            result = await self.db.execute(stmt)
            resolved = result.scalar() or 0
            assigned = team["assigned_issues"]
            team["resolved_issues"] = resolved
            team["resolution_rate"] = round((resolved / assigned) if assigned > 0 else 0.0, 2)

        teams.sort(key=lambda t: t["resolution_rate"], reverse=True)
        return teams[:limit]

    async def _count_issues(self, filters: list) -> int:
        """Count issues with given filters."""
        stmt = select(func.count(Issue.issue_id))
        for f in filters:
            stmt = stmt.where(f)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _count_users(self) -> int:
        """Count total users."""
        result = await self.db.execute(select(func.count(User.user_id)))
        return result.scalar() or 0

    async def _count_citizens(self) -> int:
        """Count total citizens."""
        result = await self.db.execute(select(func.count(Citizen.citizen_id)))
        return result.scalar() or 0

    async def _count_employees(self) -> int:
        """Count total employees."""
        result = await self.db.execute(select(func.count(Employee.employee_id)))
        return result.scalar() or 0
