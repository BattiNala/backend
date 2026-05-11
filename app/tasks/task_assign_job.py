"""
task assign Job utilities for the application.
"""

import time

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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


async def assign_issue_to_nearest_employee(  # pylint: disable=too-many-return-statements,too-many-statements
    issue_id: int,
) -> None:
    """Assign an issue to the nearest available team's available employee."""
    async with AsyncSessionLocal() as db:
        start_time = time.monotonic()
        logger.info("Starting issue auto-assignment for issue_id=%s", issue_id)

        try:
            result = await db.execute(
                select(Issue)
                .options(joinedload(Issue.issue_location))
                .where(Issue.issue_id == issue_id)
            )
        except SQLAlchemyError:
            logger.exception("DB error fetching issue for issue_id=%s", issue_id)
            return

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
                "Issue auto-assignment skipped: issue_id=%s has invalid coordinates"
                " latitude=%s longitude=%s",
                issue_id,
                getattr(issue.issue_location, "latitude", None),
                getattr(issue.issue_location, "longitude", None),
            )
            return

        logger.debug("Parsed issue location for issue_id=%s: %s", issue_id, issue_location)

        try:
            teams_result = await db.execute(
                select(Team).where(Team.department_id == issue.issue_type)
            )
        except SQLAlchemyError:
            logger.exception(
                "DB error fetching teams for department_id=%s (issue_id=%s)",
                issue.issue_type,
                issue_id,
            )
            return

        teams = teams_result.scalars().all()

        if not teams:
            logger.info(
                "Issue auto-assignment skipped: issue_id=%s has no teams for department_id=%s",
                issue_id,
                issue.issue_type,
            )
            return

        def team_distance(team: Team) -> float:
            try:
                return haversine(
                    issue_location,
                    GeoLocation(
                        latitude=float(team.base_latitude), longitude=float(team.base_longitude)
                    ),
                )
            except (TypeError, ValueError, OSError):
                logger.exception(
                    "Failed to compute distance for team_id=%s (issue_id=%s)",
                    getattr(team, "team_id", None),
                    issue_id,
                )
                return float("inf")

        teams_with_distance = [(team, team_distance(team)) for team in teams]
        teams_sorted = [t for t, _ in sorted(teams_with_distance, key=lambda td: td[1])]

        logger.info(
            "Teams found for department_id=%s (issue_id=%s): %s",
            issue.issue_type,
            issue_id,
            [(t.team_id, d) for t, d in teams_with_distance],
        )

        for team in teams_sorted:
            if not team.status:
                continue

            try:
                employee_result = await db.execute(
                    select(Employee)
                    .where(
                        Employee.team_id == team.team_id,
                        Employee.current_status == EmployeeActivityStatus.AVAILABLE,
                    )
                    .order_by(Employee.employee_id)
                    .limit(1)
                )
            except SQLAlchemyError:
                logger.exception(
                    "DB error fetching employee for team_id=%s (issue_id=%s)",
                    team.team_id,
                    issue_id,
                )
                continue

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
            except SQLAlchemyError:
                await db.rollback()
                logger.exception(
                    "Issue auto-assignment failed during commit: issue_id=%s "
                    "employee_id=%s team_id=%s",
                    issue_id,
                    employee.employee_id,
                    team.team_id,
                )
                raise

            duration = time.monotonic() - start_time
            logger.info(
                "Issue auto-assigned successfully: issue_id=%s issue_label=%s employee_id=%s "
                "team_id=%s department_id=%s duration=%.3fs",
                issue_id,
                issue.issue_label,
                employee.employee_id,
                team.team_id,
                issue.issue_type,
                duration,
            )
            return

        logger.info(
            "Issue auto-assignment pending: issue_id=%s no available employee found for "
            "department_id=%s",
            issue_id,
            issue.issue_type,
        )
