"""
Return wrapper functions for issue-related operations.
"""

from app.models.issue import Issue
from app.schemas.issue import IssueDetailResponse
from app.utils.time import utc_to_timezone


def wrap_issue_detail_response(issue: Issue):
    """Wrap an Issue object into an IssueDetailResponse schema."""
    return IssueDetailResponse(
        issue_label=issue.issue_label,
        issue_type=issue.department.department_name if issue.department else "Unknown",
        description=issue.description,
        status=issue.status,
        issue_priority=issue.issue_priority,
        assigned_to=issue.assignee.name if issue.assignee else None,
        created_at=str(utc_to_timezone(issue.created_at)),
        attachments=[attachment.path for attachment in issue.attachments],
        issue_location=issue.issue_location.address if issue.issue_location else None,
        latitude=issue.issue_location.latitude if issue.issue_location else None,
        longitude=issue.issue_location.longitude if issue.issue_location else None,
    )
