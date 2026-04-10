"""
Return wrapper functions for issue-related operations.
"""

from app.models.issue import Issue
from app.schemas.issue import IssueDetailResponse
from app.utils.time import utc_to_timezone


def _get_rejected_reason(issue: Issue) -> str | None:
    """Return the rejection reason from either scalar or list relationships."""
    rejected_issue = issue.rejected_issues
    if not rejected_issue:
        return None
    if isinstance(rejected_issue, list):
        rejected_issue = rejected_issue[0] if rejected_issue else None
    return rejected_issue.reason if rejected_issue else None


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
        rejected_reason=_get_rejected_reason(issue),
    )
