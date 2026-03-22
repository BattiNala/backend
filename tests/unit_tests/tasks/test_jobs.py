"""Tests for background job utilities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.issue import IssueStatus
from app.tasks import jobs


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

    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(jobs, "haversine", lambda *_args: 0.0)
    monkeypatch.setattr(jobs.logger, "info", info)
    monkeypatch.setattr(jobs.logger, "warning", Mock())
    monkeypatch.setattr(jobs.logger, "exception", Mock())

    asyncio.run(jobs.assign_issue_to_nearest_employee(issue.issue_id))

    assert issue.assignee_id == employee.employee_id
    assert issue.status == IssueStatus.IN_PROGRESS
    assert employee.current_status == jobs.EmployeeActivityStatus.BUSY
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

    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(jobs, "haversine", lambda *_args: 0.0)
    monkeypatch.setattr(jobs.logger, "info", info)
    monkeypatch.setattr(jobs.logger, "warning", Mock())
    monkeypatch.setattr(jobs.logger, "exception", Mock())

    asyncio.run(jobs.assign_issue_to_nearest_employee(issue.issue_id))

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
