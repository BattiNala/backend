"""
task assign Job utilities for the application.
"""

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.logger import get_logger
from app.db.session import AsyncSessionLocal
from app.models.employee import Employee
from app.models.issue import Issue
from app.models.team import Team
from app.routing.haversine import haversine
from app.schemas.employee import EmployeeActivityStatus
from app.schemas.geo_location import GeoLocation
from app.schemas.issue import IssueStatus

logger = get_logger("tasks.assign_job")


async def assign_issue_to_nearest_employee(issue_id: int) -> None:
    """Assign an issue to the nearest available team's available employee."""
    async with AsyncSessionLocal() as db:
        logger.info("Starting issue auto-assignment for issue_id=%s", issue_id)

        result = await db.execute(
            select(Issue)
            .options(joinedload(Issue.issue_location))
            .where(Issue.issue_id == issue_id)
        )
        issue = result.scalars().first()

        if not issue:
            logger.warning("Issue auto-assignment skipped: issue_id=%s not found", issue_id)
            return

        if issue.assignee_id is not None:
            logger.info(
                "Issue auto-assignment skipped: issue_id=%s already assigned to employee_id=%s",
                issue_id,
                issue.assignee_id,
            )
            return

        if not issue.issue_location:
            logger.warning("Issue auto-assignment skipped: issue_id=%s has no location", issue_id)
            return

        try:
            issue_location = GeoLocation(
                latitude=float(issue.issue_location.latitude),
                longitude=float(issue.issue_location.longitude),
            )
        except (TypeError, ValueError):
            logger.warning(
                "Issue auto-assignment skipped: issue_id=%s has invalid coordinates "
                "latitude=%s longitude=%s",
                issue_id,
                getattr(issue.issue_location, "latitude", None),
                getattr(issue.issue_location, "longitude", None),
            )
            return

        teams_result = await db.execute(select(Team).where(Team.department_id == issue.issue_type))
        teams = teams_result.scalars().all()

        if not teams:
            logger.info(
                "Issue auto-assignment skipped: issue_id=%s has no teams for department_id=%s",
                issue_id,
                issue.issue_type,
            )
            return

        def team_distance(team: Team) -> float:
            return haversine(
                issue_location,
                GeoLocation(
                    latitude=float(team.base_latitude),
                    longitude=float(team.base_longitude),
                ),
            )

        teams_sorted = sorted(teams, key=team_distance)

        for team in teams_sorted:
            if not team.status:
                continue

            employee_result = await db.execute(
                select(Employee)
                .where(
                    Employee.team_id == team.team_id,
                    Employee.current_status == EmployeeActivityStatus.AVAILABLE,
                )
                .order_by(Employee.employee_id)
                .limit(1)
            )
            employee = employee_result.scalars().first()

            if not employee:
                continue

            issue.assignee_id = employee.employee_id
            issue.status = IssueStatus.IN_PROGRESS
            employee.current_status = EmployeeActivityStatus.BUSY

            db.add(employee)
            db.add(issue)

            try:
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception(
                    "Issue auto-assignment failed during commit: issue_id=%s employee_id=%s"
                    " team_id=%s",
                    issue_id,
                    employee.employee_id,
                    team.team_id,
                )
                raise

            logger.info(
                "Issue auto-assigned successfully: issue_id=%s issue_label=%s "
                "employee_id=%s team_id=%s department_id=%s",
                issue_id,
                issue.issue_label,
                employee.employee_id,
                team.team_id,
                issue.issue_type,
            )
            return

        logger.info(
            "Issue auto-assignment pending: issue_id=%s no available employee found for "
            "department_id=%s",
            issue_id,
            issue.issue_type,
        )
