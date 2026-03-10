"""
Issue repository for handling database operations related to issues.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.issue import Issue
from app.models.issue_location import IssueLocation
from app.schemas.issue import AnonymousIssueCreate, IssueCreate, IssueStatus


class IssueRepository:
    """Repository for managing issue-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db: AsyncSession = db

    async def check_issue_label_exists(self, issue_label: str) -> bool:
        """Check if an issue label already exists in the database."""
        result = await self.db.execute(select(Issue).where(Issue.issue_label == issue_label))
        return result.scalars().first() is not None

    async def create_anon_issue(self, issue_data: AnonymousIssueCreate, issue_label: str):
        """Create a new anonymous issue in the database."""
        new_issue = Issue(
            issue_label=issue_label,
            issue_type=issue_data.issue_type,
            description=issue_data.description,
            status=IssueStatus.PENDING_VERIFICATION,
            is_anonymous=True,
            issue_location=IssueLocation(
                latitude=str(issue_data.latitude),
                longitude=str(issue_data.longitude),
                address=issue_data.issue_location,
            ),
        )
        self.db.add(new_issue)
        await self.db.commit()
        await self.db.refresh(new_issue)
        return new_issue

    async def create_issue(self, issue_data: IssueCreate, user_id: int, issue_label: str):
        """Create a new issue in the database."""
        new_issue = Issue(
            issue_label=issue_label,
            issue_type=issue_data.issue_type,
            description=issue_data.description,
            status=issue_data.status,
            is_anonymous=False,
            reporter_id=user_id,
            issue_location=IssueLocation(
                latitude=str(issue_data.latitude),
                longitude=str(issue_data.longitude),
                address=issue_data.issue_location,
            ),
        )
        self.db.add(new_issue)
        await self.db.commit()
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
            .where(Issue.issue_label == issue_label)
        )
        result = await self.db.execute(stmt)
        issue = result.scalars().first()

        if not issue:
            return None
        return issue

    async def list_issues(self):
        """List all issues."""
        result = await self.db.execute(select(Issue))
        return result.scalars().all()
