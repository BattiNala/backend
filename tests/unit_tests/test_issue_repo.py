"""Tests for issue repository."""

import asyncio

from app.repositories import issue_repo
from app.schemas.issue import IssueCreate, IssueStatus

# pylint: disable=too-few-public-methods


class _FakeSession:
    """Minimal async session test double."""

    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshes = []

    def add(self, obj):
        """Store added objects."""
        self.added.append(obj)

    async def commit(self):
        """Track commits."""
        self.commits += 1

    async def refresh(self, obj):
        """Track refreshes."""
        self.refreshes.append(obj)


class _FakeIssueLocation:
    """Simple issue location value object."""

    def __init__(self, latitude, longitude, address):
        self.latitude = latitude
        self.longitude = longitude
        self.address = address


class _FakeAttachment:
    """Simple attachment value object."""

    def __init__(self, path):
        self.path = path


class _FakeIssue:
    """Simple issue value object."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_create_issue_sets_open_status(monkeypatch):
    """Authenticated issue creation defaults to OPEN status."""
    monkeypatch.setattr(issue_repo, "Issue", _FakeIssue)
    monkeypatch.setattr(issue_repo, "IssueLocation", _FakeIssueLocation)
    monkeypatch.setattr(issue_repo, "Attachment", _FakeAttachment)

    db = _FakeSession()
    repo = issue_repo.IssueRepository(db)
    issue_data = IssueCreate(
        issue_type=1,
        description="Broken streetlight",
        latitude=27.7,
        longitude=85.3,
    )

    created = asyncio.run(repo.create_issue(issue_data, user_id=7, issue_label="ISS-123"))

    assert created.status == IssueStatus.OPEN
    assert created.reporter_id == 7
    assert db.added == [created]
    assert db.commits == 1
    assert db.refreshes == [created]
