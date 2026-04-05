"""
Issue repository for handling database operations related to issues.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.attachment import Attachment
from app.models.employee import Employee
from app.models.issue import Issue
from app.models.issue_location import IssueLocation
from app.models.issue_reports import IssueReport
from app.models.rejected_issue import RejectedIssue
from app.schemas.attachment import AttachmentCreatePayload
from app.schemas.employee import EmployeeActivityStatus
from app.schemas.issue import (
    AnonymousIssueCreate,
    IssueCreate,
    IssueListFilters,
    IssueListItem,
    IssueStatus,
)
from app.utils.time import utc_to_timezone


class IssueRepository:
    """Repository for managing issue-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db: AsyncSession = db

    async def check_issue_label_exists(self, issue_label: str) -> bool:
        """Check if an issue label already exists in the database."""
        result = await self.db.execute(select(Issue).where(Issue.issue_label == issue_label))
        return result.scalars().first() is not None

    async def create_anon_issue(
        self,
        issue_data: AnonymousIssueCreate,
        issue_label: str,
        attachments: list[AttachmentCreatePayload] | None = None,
    ):
        """Create a new anonymous issue in the database."""
        new_issue = Issue(
            issue_label=issue_label,
            issue_type=issue_data.issue_type,
            description=issue_data.description,
            issue_priority=issue_data.issue_priority,
            status=IssueStatus.PENDING_VERIFICATION,
            is_anonymous=True,
            issue_location=IssueLocation(
                latitude=str(issue_data.latitude),
                longitude=str(issue_data.longitude),
                address=issue_data.issue_location,
            ),
            attachments=[
                Attachment(path=attachment["path"], phash=attachment["phash"])
                for attachment in (attachments or [])
            ],
        )
        self.db.add(new_issue)
        await self.db.flush()
        await self.db.refresh(new_issue)
        return new_issue

    async def create_issue(
        self,
        issue_data: IssueCreate,
        user_id: int,
        issue_label: str,
        attachments: list[AttachmentCreatePayload] | None = None,
    ) -> Issue:
        """Create a new issue in the database."""
        new_issue = Issue(
            issue_label=issue_label,
            issue_type=issue_data.issue_type,
            description=issue_data.description,
            issue_priority=issue_data.issue_priority,
            status=IssueStatus.OPEN,
            is_anonymous=False,
            reporter_id=user_id,
            issue_location=IssueLocation(
                latitude=str(issue_data.latitude),
                longitude=str(issue_data.longitude),
                address=issue_data.issue_location,
            ),
            attachments=[
                Attachment(path=attachment["path"], phash=attachment["phash"])
                for attachment in (attachments or [])
            ],
        )
        self.db.add(new_issue)
        await self.db.flush()
        await self.db.refresh(new_issue)
        return new_issue

    async def get_issue_by_id(self, issue_id: int) -> Issue:
        """Get an issue by its ID, including its location information."""
        stmt = (
            select(Issue)
            .options(joinedload(Issue.issue_location))
            .where(Issue.issue_id == issue_id)
        )
        result = await self.db.execute(stmt)
        issue = result.scalars().first()

        if not issue:
            return None

        if not issue.issue_location:
            raise ValueError(f"Issue {issue_id} has no location, but location is mandatory.")

        return issue

    async def get_issue_location(self, issue_id: int) -> IssueLocation:
        """Get the location information for a specific issue."""
        stmt = select(IssueLocation).where(IssueLocation.issue_id == issue_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_issue_by_label(self, issue_label: str) -> Issue:
        """Get an issue by its label."""
        stmt = (
            select(Issue)
            .options(joinedload(Issue.issue_location))
            .options(joinedload(Issue.attachments))
            .options(joinedload(Issue.department))
            .options(joinedload(Issue.reporter))
            .options(joinedload(Issue.assignee))
            .where(Issue.issue_label == issue_label)
        )
        result = await self.db.execute(stmt)
        issue = result.scalars().first()

        if not issue:
            return None
        return issue

    async def update_issue_status(self, issue: Issue, status: IssueStatus) -> Issue:
        """Update the status for an issue."""
        issue.status = status
        self.db.add(issue)
        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def list_issues(self, filters: IssueListFilters | None = None) -> List[IssueListItem]:
        """List issues with optional filters."""
        filters = filters or IssueListFilters()
        stmt = select(Issue).options(joinedload(Issue.department))
        if filters.department_id is not None:
            stmt = stmt.where(Issue.issue_type == filters.department_id)
        if filters.assignee_id is not None:
            stmt = stmt.where(Issue.assignee_id == filters.assignee_id)
        if filters.reporter_id is not None:
            stmt = stmt.where(Issue.reporter_id == filters.reporter_id)
        if filters.status is not None:
            stmt = stmt.where(Issue.status == filters.status)
        if filters.priority is not None:
            stmt = stmt.where(Issue.issue_priority == filters.priority)
        if filters.date_from is not None:
            stmt = stmt.where(Issue.created_at >= filters.date_from)
        if filters.date_to is not None:
            stmt = stmt.where(Issue.created_at <= filters.date_to)
        result = await self.db.execute(stmt)
        selected_issues = result.scalars().all()
        return [
            IssueListItem(
                issue_label=issue.issue_label,
                issue_type=issue.department.department_name
                if issue.department
                else str(issue.issue_type),
                issue_priority=issue.issue_priority,
                description=issue.description,
                status=issue.status,
                created_at=str(utc_to_timezone(issue.created_at)),
            )
            for issue in selected_issues
        ]

    async def get_issues_by_reporter(self, reporter_id: int) -> list[IssueListItem]:
        """List all issues reported by a specific user."""
        result = await self.db.execute(
            select(Issue)
            .options(joinedload(Issue.department))
            .where(Issue.reporter_id == reporter_id)
        )
        issues = result.scalars().all()
        return [
            IssueListItem(
                issue_label=issue.issue_label,
                issue_type=issue.department.department_name
                if issue.department
                else str(issue.issue_type),
                issue_priority=issue.issue_priority,
                description=issue.description,
                status=issue.status,
                created_at=str(utc_to_timezone(issue.created_at)),
            )
            for issue in issues
        ]

    async def report_issue_as_false(
        self, issue: Issue, reason: str, reported_by_employee_id: int
    ) -> Issue:
        """Report an issue as false with a reason and employee information."""

        reported_issue = IssueReport(
            issue_id=issue.issue_id,
            description=reason,
            reported_by=reported_by_employee_id,
        )
        self.db.add(reported_issue)
        await self.db.flush()
        await self.db.refresh(reported_issue)

        issue.status = IssueStatus.PENDING_VERIFICATION
        issue.assignee_id = None
        employee: Employee | None = None
        if reported_by_employee_id:
            employee_result = await self.db.execute(
                select(Employee).where(Employee.employee_id == reported_by_employee_id)
            )
            employee = employee_result.scalars().first()
            if employee and employee.current_status == EmployeeActivityStatus.BUSY:
                employee.current_status = EmployeeActivityStatus.AVAILABLE
                self.db.add(employee)
        self.db.add(issue)
        await self.db.commit()
        await self.db.refresh(issue)

        return issue

    async def reject_issue(
        self,
        issue: Issue,
        reason: str,
        rejected_by_employee_id: int | None = None,
        auto_reject: bool = False,
    ) -> Issue:
        """Reject an issue with a reason and optional employee information."""

        rejected_issue = RejectedIssue(
            issue_id=issue.issue_id,
            reason=reason,
            rejected_by=rejected_by_employee_id,
            auto_rejected=auto_reject,
        )
        self.db.add(rejected_issue)
        await self.db.flush()
        await self.db.refresh(rejected_issue)

        issue.status = IssueStatus.REJECTED
        issue.assignee_id = None

        self.db.add(issue)
        await self.db.commit()
        await self.db.refresh(issue)

        return issue
