"""Service for finding nearby issues based on geolocation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.issue import Issue
from app.models.issue_location import IssueLocation
from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation
from app.schemas.issue import IssueStatus


class IssueProximityService:  # pylint: disable=too-few-public-methods
    """Service for finding nearby issues based on geolocation."""

    @staticmethod
    async def get_nearby_candidate_issues(
        db: AsyncSession,
        issue: Issue,
        radius_meters: float = 30.0,
        limit: int = 20,
    ) -> list[Issue]:
        """
        Return nearby candidate issues for duplicate checking.
        """
        if not issue.issue_location:
            return []

        source_location = GeoLocation(
            latitude=float(issue.issue_location.latitude),
            longitude=float(issue.issue_location.longitude),
        )

        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.issue_location),
                selectinload(Issue.attachments),
            )
            .join(IssueLocation, Issue.issue_id == IssueLocation.issue_id)
            .where(Issue.issue_id != issue.issue_id)
            .where(Issue.issue_type == issue.issue_type)
            .where(
                Issue.status.in_(
                    [
                        IssueStatus.OPEN,
                        IssueStatus.PENDING_VERIFICATION,
                        IssueStatus.IN_PROGRESS,
                    ]
                )
            )
            .limit(200)
        )

        result = await db.execute(stmt)
        candidate_issues = result.scalars().unique().all()

        nearby: list[tuple[Issue, float]] = []

        for candidate in candidate_issues:
            if not candidate.issue_location:
                continue

            candidate_lat: float = float(candidate.issue_location.latitude)
            candidate_lon: float = float(candidate.issue_location.longitude)
            candidate_location = GeoLocation(latitude=candidate_lat, longitude=candidate_lon)

            distance_m: float = haversine(source_location, candidate_location)

            if distance_m <= radius_meters:
                nearby.append((candidate, distance_m))

        nearby.sort(key=lambda item: item[1])

        return [issue for issue, _distance in nearby[:limit]]
