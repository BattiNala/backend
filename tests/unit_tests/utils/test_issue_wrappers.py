"""Tests for issue response wrappers."""

from types import SimpleNamespace

from app.schemas.issue import IssuePriority, IssueStatus
from app.utils.return_wrappers.issues import wrap_issue_detail_response


def _build_issue(rejected_issues):
    """Build a minimal issue object for wrapper tests."""
    return SimpleNamespace(
        issue_label="I-123",
        department=SimpleNamespace(department_name="Roads"),
        description="Broken curb",
        status=IssueStatus.REJECTED,
        issue_priority=IssuePriority.NORMAL,
        assignee=None,
        created_at=None,
        attachments=[SimpleNamespace(path="/tmp/photo.jpg")],
        issue_location=SimpleNamespace(address="Main St", latitude=27.7, longitude=85.3),
        rejected_issues=rejected_issues,
    )


def test_wrap_issue_detail_response_uses_scalar_rejected_issue(monkeypatch):
    """Wrapper returns the rejection reason from the one-to-one relationship."""
    monkeypatch.setattr(
        "app.utils.return_wrappers.issues.utc_to_timezone",
        lambda value: value,
    )
    issue = _build_issue(SimpleNamespace(reason="Duplicate report"))

    response = wrap_issue_detail_response(issue)

    assert response.rejected_reason == "Duplicate report"


def test_wrap_issue_detail_response_tolerates_list_rejected_issue(monkeypatch):
    """Wrapper should not crash if an older mapping still provides a list."""
    monkeypatch.setattr(
        "app.utils.return_wrappers.issues.utc_to_timezone",
        lambda value: value,
    )
    issue = _build_issue([SimpleNamespace(reason="Spam report")])

    response = wrap_issue_detail_response(issue)

    assert response.rejected_reason == "Spam report"
