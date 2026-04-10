"""Tests for background job utilities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.schemas.issue import IssueStatus
from app.tasks import image_jobs, jobs, task_assign_job


class _Scalars:
    """Minimal SQLAlchemy scalars() test double."""

    def __init__(self, value):
        self._value = value

    def first(self):
        """Return the first scalar result."""
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def all(self):
        """Return all scalar results."""
        if isinstance(self._value, list):
            return self._value
        return [] if self._value is None else [self._value]


class _Result:  # pylint: disable=too-few-public-methods
    """Minimal SQLAlchemy result test double."""

    def __init__(self, value):
        self._value = value

    def scalars(self):
        """Return a scalars wrapper."""
        return _Scalars(self._value)


class _FakeSession:
    """Async session test double for assignment jobs."""

    def __init__(self, results):
        self._results = iter(results)
        self.added = []
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context."""
        return None

    async def execute(self, _stmt):
        """Return queued results for each execute call."""
        return _Result(next(self._results))

    def add(self, instance):
        """Track added instances."""
        self.added.append(instance)

    async def commit(self):
        """Track commit calls."""
        self.committed = True

    async def rollback(self):
        """Track rollback calls."""
        self.rolled_back = True


def test_assign_issue_to_nearest_employee_logs_successful_assignment(monkeypatch):
    """Test successful auto-assignment emits an info log after commit."""
    issue = SimpleNamespace(
        issue_id=17,
        issue_label="ISS-17",
        assignee_id=None,
        issue_type=4,
        status=IssueStatus.OPEN,
        issue_location=SimpleNamespace(latitude="27.7000", longitude="85.3000"),
    )
    team = SimpleNamespace(
        team_id=9,
        status=True,
        base_latitude=27.7000,
        base_longitude=85.3000,
    )
    employee = SimpleNamespace(employee_id=12, current_status=None)
    session = _FakeSession([issue, [team], employee])
    info = Mock()

    monkeypatch.setattr(task_assign_job, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(task_assign_job, "haversine", lambda *_args: 0.0)
    monkeypatch.setattr(task_assign_job.logger, "info", info)
    monkeypatch.setattr(task_assign_job.logger, "warning", Mock())
    monkeypatch.setattr(task_assign_job.logger, "exception", Mock())

    asyncio.run(task_assign_job.assign_issue_to_nearest_employee(issue.issue_id))

    assert issue.assignee_id == employee.employee_id
    assert issue.status == IssueStatus.IN_PROGRESS
    assert employee.current_status == task_assign_job.EmployeeActivityStatus.BUSY
    assert session.added == [employee, issue]
    assert session.committed is True
    assert session.rolled_back is False
    info.assert_any_call(
        (
            "Issue auto-assigned successfully: issue_id=%s issue_label=%s "
            "employee_id=%s team_id=%s department_id=%s"
        ),
        17,
        "ISS-17",
        12,
        9,
        4,
    )


def test_assign_issue_to_nearest_employee_logs_pending_when_no_employee(monkeypatch):
    """Test pending auto-assignment is logged when no employee is available."""
    issue = SimpleNamespace(
        issue_id=18,
        issue_label="ISS-18",
        assignee_id=None,
        issue_type=5,
        status=IssueStatus.OPEN,
        issue_location=SimpleNamespace(latitude="27.7100", longitude="85.3100"),
    )
    team = SimpleNamespace(
        team_id=10,
        status=True,
        base_latitude=27.7000,
        base_longitude=85.3000,
    )
    session = _FakeSession([issue, [team], None])
    info = Mock()

    monkeypatch.setattr(task_assign_job, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(task_assign_job, "haversine", lambda *_args: 0.0)
    monkeypatch.setattr(task_assign_job.logger, "info", info)
    monkeypatch.setattr(task_assign_job.logger, "warning", Mock())
    monkeypatch.setattr(task_assign_job.logger, "exception", Mock())

    asyncio.run(task_assign_job.assign_issue_to_nearest_employee(issue.issue_id))

    assert issue.assignee_id is None
    assert issue.status == IssueStatus.OPEN
    assert not session.added
    assert session.committed is False
    info.assert_any_call(
        (
            "Issue auto-assignment pending: issue_id=%s "
            "no available employee found for department_id=%s"
        ),
        18,
        5,
    )


def test_validate_issue_images_accepts_strong_match(monkeypatch):
    """Accepted image validation returns accepted without mutating issue state."""
    issue = SimpleNamespace(
        issue_id=13,
        description="Large pothole on the road",
        department=SimpleNamespace(department_name="Roads"),
        attachments=[SimpleNamespace(path="uploads/photo.jpg")],
    )
    issue_repo = Mock()
    verification_response = SimpleNamespace(
        ok=True,
        result=SimpleNamespace(verdict="strong_match", score=95),
        message=None,
    )

    monkeypatch.setattr(
        jobs, "return_attachment_urls", lambda _issue: ["https://example.com/photo"]
    )
    monkeypatch.setattr(jobs, "llm_verify", AsyncMock(return_value=verification_response))
    monkeypatch.setattr(
        jobs,
        "should_auto_accept",
        lambda result: (result.verdict, result.score) == ("strong_match", 95),
    )
    monkeypatch.setattr(jobs, "should_reject", lambda _result: False)

    status = asyncio.run(jobs.validate_issue_images(issue_repo, issue))

    assert status == "accepted"
    issue_repo.reject_issue.assert_not_called()
    issue_repo.update_issue_status.assert_not_called()


def test_validate_issue_images_rejects_weak_match(monkeypatch):
    """Rejected image validation persists a rejected outcome."""
    issue = SimpleNamespace(
        issue_id=21,
        description="Image does not match the report",
        department=SimpleNamespace(department_name="Sanitation"),
        attachments=[SimpleNamespace(path="uploads/photo.jpg")],
    )
    issue_repo = Mock()
    issue_repo.reject_issue = AsyncMock()
    verification_response = SimpleNamespace(
        ok=True,
        result=SimpleNamespace(
            verdict="irrelevant_or_unusable",
            score=5,
            rationale="Image is unrelated",
        ),
        message="Image is unrelated",
    )

    monkeypatch.setattr(
        jobs, "return_attachment_urls", lambda _issue: ["https://example.com/photo"]
    )
    monkeypatch.setattr(jobs, "llm_verify", AsyncMock(return_value=verification_response))
    monkeypatch.setattr(jobs, "should_auto_accept", lambda _result: False)
    monkeypatch.setattr(
        jobs,
        "should_reject",
        lambda result: (result.verdict, result.score) == ("irrelevant_or_unusable", 5),
    )

    status = asyncio.run(jobs.validate_issue_images(issue_repo, issue))

    assert status == "rejected"
    issue_repo.reject_issue.assert_awaited_once_with(
        issue,
        reason="Rejected by LLMImage is unrelated",
        auto_reject=True,
    )


def test_validate_issue_images_marks_manual_review(monkeypatch):
    """Borderline image validation moves the issue to manual review."""
    issue = SimpleNamespace(
        issue_id=34,
        description="Image is somewhat unclear",
        department=SimpleNamespace(department_name="Roads"),
        attachments=[SimpleNamespace(path="uploads/photo.jpg")],
    )
    issue_repo = Mock()
    issue_repo.update_issue_status = AsyncMock()
    verification_response = SimpleNamespace(
        ok=True,
        result=SimpleNamespace(verdict="moderate_match", score=65),
        message=None,
    )

    monkeypatch.setattr(
        jobs, "return_attachment_urls", lambda _issue: ["https://example.com/photo"]
    )
    monkeypatch.setattr(jobs, "llm_verify", AsyncMock(return_value=verification_response))
    monkeypatch.setattr(jobs, "should_auto_accept", lambda _result: False)
    monkeypatch.setattr(jobs, "should_reject", lambda _result: False)

    status = asyncio.run(jobs.validate_issue_images(issue_repo, issue))

    assert status == "manual_review"
    issue_repo.update_issue_status.assert_awaited_once_with(
        issue,
        status=IssueStatus.PENDING_VERIFICATION,
    )


def test_get_best_orb_match_between_issues_downloads_s3_backed_attachments(monkeypatch, tmp_path):
    """ORB comparison should resolve S3 object keys to local temp files first."""
    downloaded_new = tmp_path / "new.jpg"
    downloaded_old = tmp_path / "old.jpg"
    downloaded_new.write_bytes(b"new")
    downloaded_old.write_bytes(b"old")

    new_issue = SimpleNamespace(
        attachments=[SimpleNamespace(attachment_id=1, path="images/new.jpg")],
    )
    candidate_issue = SimpleNamespace(
        attachments=[SimpleNamespace(attachment_id=2, path="images/old.jpg")],
    )

    async def _fake_download(object_key):
        return str(downloaded_new if object_key == "images/new.jpg" else downloaded_old)

    cleanup = AsyncMock()
    compute = Mock(
        return_value={
            "good_matches": 24,
            "total_matches": 30,
            "similarity_score": 0.31,
        }
    )

    monkeypatch.setattr(image_jobs, "download_s3_object_to_tempfile", _fake_download)
    monkeypatch.setattr(image_jobs, "delete_temp_files", cleanup)
    monkeypatch.setattr(image_jobs.IssueImageValidationService, "compute_orb_similarity", compute)

    result = asyncio.run(image_jobs.get_best_orb_match_between_issues(new_issue, candidate_issue))

    assert result == {
        "new_attachment_id": 1,
        "old_attachment_id": 2,
        "good_matches": 24,
        "similarity_score": 0.31,
    }
    compute.assert_called_once_with(str(downloaded_new), str(downloaded_old))
    cleanup.assert_awaited_once_with([str(downloaded_new), str(downloaded_old)])


def test_get_best_orb_match_between_issues_reuses_existing_local_paths(monkeypatch, tmp_path):
    """Existing local attachment paths should bypass storage downloads."""
    local_new = tmp_path / "new.jpg"
    local_old = tmp_path / "old.jpg"
    local_new.write_bytes(b"new")
    local_old.write_bytes(b"old")

    new_issue = SimpleNamespace(
        attachments=[SimpleNamespace(attachment_id=1, path=str(local_new))],
    )
    candidate_issue = SimpleNamespace(
        attachments=[SimpleNamespace(attachment_id=2, path=str(local_old))],
    )

    cleanup = AsyncMock()
    download = AsyncMock()
    compute = Mock(
        return_value={
            "good_matches": 18,
            "total_matches": 25,
            "similarity_score": 0.2,
        }
    )

    monkeypatch.setattr(image_jobs, "download_s3_object_to_tempfile", download)
    monkeypatch.setattr(image_jobs, "delete_temp_files", cleanup)
    monkeypatch.setattr(image_jobs.IssueImageValidationService, "compute_orb_similarity", compute)

    result = asyncio.run(image_jobs.get_best_orb_match_between_issues(new_issue, candidate_issue))

    assert result == {
        "new_attachment_id": 1,
        "old_attachment_id": 2,
        "good_matches": 18,
        "similarity_score": 0.2,
    }
    download.assert_not_awaited()
    compute.assert_called_once_with(str(local_new), str(local_old))
    cleanup.assert_awaited_once_with([])
