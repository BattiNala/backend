"""Analytics schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel


class AnalyticsFilters(BaseModel):
    """Filters for analytics queries."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    department_id: int | None = None


class IssueStatusBreakdown(BaseModel):
    """Breakdown of issues by status."""

    status: str
    count: int


class IssuePriorityBreakdown(BaseModel):
    """Breakdown of issues by priority."""

    priority: str
    count: int


class IssueStatsResponse(BaseModel):
    """Overall issue statistics."""

    total_issues: int
    open_issues: int
    in_progress_issues: int
    resolved_issues: int
    rejected_issues: int
    pending_verification_issues: int
    status_breakdown: list[IssueStatusBreakdown]
    priority_breakdown: list[IssuePriorityBreakdown]


class DepartmentIssueStats(BaseModel):
    """Issue statistics for a single department."""

    department_id: int
    department_name: str
    total_issues: int
    open_issues: int
    resolved_issues: int
    avg_resolution_time_hours: float | None = None


class DepartmentAnalyticsResponse(BaseModel):
    """Department-wise analytics."""

    departments: list[DepartmentIssueStats]
    total_departments: int


class EmployeePerformanceStats(BaseModel):
    """Performance stats for a single employee."""

    employee_id: int
    name: str
    department_name: str
    total_assigned: int
    resolved_count: int
    in_progress_count: int
    resolution_rate: float


class EmployeeAnalyticsResponse(BaseModel):
    """Employee performance analytics."""

    employees: list[EmployeePerformanceStats]
    total_employees: int
    avg_resolution_rate: float


class DailyIssueTrend(BaseModel):
    """Daily issue trend data point."""

    date: str
    count: int


class IssueTrendResponse(BaseModel):
    """Issue trend over time."""

    trend: list[DailyIssueTrend]
    total_days: int


class UserRoleDistribution(BaseModel):
    """User count by role."""

    role_name: str
    count: int


class UserStatsResponse(BaseModel):
    """Overall user statistics."""

    total_users: int
    total_citizens: int
    total_employees: int
    role_distribution: list[UserRoleDistribution]


class TeamWorkloadStats(BaseModel):
    """Workload stats for a single team."""

    team_id: int
    team_name: str
    department_name: str
    total_members: int
    available_members: int
    busy_members: int
    assigned_issues: int


class TeamAnalyticsResponse(BaseModel):
    """Team workload analytics."""

    teams: list[TeamWorkloadStats]
    total_teams: int


class TopEmployeeStats(BaseModel):
    """Top performing employee stats."""

    employee_id: int
    name: str
    department_name: str
    total_assigned: int
    resolved_count: int
    resolution_rate: float


class TopPerformingEmployeesResponse(BaseModel):
    """Top performing employees."""

    employees: list[TopEmployeeStats]


class TopTeamStats(BaseModel):
    """Top performing team stats."""

    team_id: int
    team_name: str
    department_name: str
    total_members: int
    resolved_issues: int
    assigned_issues: int
    resolution_rate: float


class TopPerformingTeamsResponse(BaseModel):
    """Top performing teams."""

    teams: list[TopTeamStats]


class DashboardSummaryResponse(BaseModel):
    """Comprehensive dashboard summary."""

    issue_stats: IssueStatsResponse
    user_stats: UserStatsResponse
    total_departments: int
    total_teams: int
    recent_issue_trend: list[DailyIssueTrend]
