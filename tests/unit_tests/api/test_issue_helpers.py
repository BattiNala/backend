"""Tests for issue helpers."""

# pylint: disable=protected-access,missing-function-docstring
# pylint: disable=too-few-public-methods,comparison-with-callable

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import BackgroundTasks

from app.api.v1.endpoints import issues
from app.schemas.issue import IssueCreate, IssueStatus, IssueStatusUpdate

ISSUE_CREATE_PAYLOAD = (
    '{"issue_type": 1, "description": "Pothole", "latitude": 27.7, "longitude": 85.3}'
)


class _UploadFile:  # pylint: disable=too-few-public-methods
    """Test double for UploadFile."""

    def __init__(self, name: str, content: bytes):
        """Init."""
        self.filename = name
        self._content = content
        self._read = False

    async def read(self, _size: int):
        """Read."""
        if self._read:
            return b""
        self._read = True
        return self._content


def _upload_file(name: str, content: bytes) -> _UploadFile:
    """Upload file."""
    return _UploadFile(name, content)


def _issue_context(db, user_id):
    """Build a minimal issue endpoint context for direct endpoint calls."""
    user = type("User", (), {"user_id": user_id})()
    return issues._IssueEndpointContext(db=db, current_user=user)


class _AsyncFile:
    """Test double for AsyncFile."""

    def __init__(self, path, mode):
        """Init."""
        self.path = Path(path)
        self.mode = mode

    async def __aenter__(self):
        """Aenter."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Aexit."""
        return None

    async def write(self, data):
        """Write."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(data)


def test_parse_issue_create_validates_json_and_schema():
    """Test parse issue create validates json and schema."""
    parsed = issues._parse_issue_create(ISSUE_CREATE_PAYLOAD, IssueCreate)

    assert parsed.issue_type == 1

    with pytest.raises(Exception) as json_exc:
        issues._parse_issue_create("{bad json", IssueCreate)
    assert json_exc.value.status_code == 400

    with pytest.raises(Exception) as validation_exc:
        issues._parse_issue_create('{"issue_type": 1}', IssueCreate)
    assert validation_exc.value.status_code == 422


def test_safe_upload_photos_to_s3_wraps_failures(monkeypatch):
    """Test safe upload photos to s3 wraps failures."""

    class _BrokenContext:
        """Test double for BrokenContext."""

        async def __aenter__(self):
            """Aenter."""
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            """Aexit."""
            return None

    def _broken_context():
        """Return a failing async context manager."""
        return _BrokenContext()

    monkeypatch.setattr(issues, "_get_s3_service", _broken_context)

    with pytest.raises(Exception) as exc:
        asyncio.run(issues._safe_upload_photos_to_s3([]))

    assert exc.value.status_code == 500


def test_upload_photos_to_s3_and_delete_temp_files(monkeypatch):
    """Test upload photos to s3 and delete temp files."""

    class _FakeS3:  # pylint: disable=too-few-public-methods
        """Test double for FakeS3."""

        def __init__(self):
            """Init."""
            self.uploaded = []

        async def upload_file(self, path):
            """Upload file."""
            self.uploaded.append(path)
            return f"stored/{path.name}"

    photos = [_upload_file("first.jpg", b"abc"), _upload_file("second.png", b"def")]
    s3 = _FakeS3()
    removed = []

    async def _remove(path):
        """Remove."""
        removed.append(path)
        Path(path).unlink(missing_ok=True)

    monkeypatch.setattr(issues.aiofiles, "open", _AsyncFile)
    monkeypatch.setattr(issues.aiofiles.os, "remove", _remove)

    attachment_paths, temp_paths = asyncio.run(issues._upload_photos_to_s3(photos, s3))

    assert attachment_paths == [f"stored/{path.split('/')[-1]}" for path in temp_paths]
    assert all(temp_path for temp_path in temp_paths)
    assert len(s3.uploaded) == 2

    asyncio.run(issues.delete_temp_files(temp_paths))
    asyncio.run(issues.delete_temp_files(temp_paths))
    assert removed == temp_paths * 2


def test_upload_photos_to_s3_cleans_up_partial_uploads(monkeypatch):
    """Test partial S3 uploads are deleted when a later upload fails."""

    class _FakeS3:  # pylint: disable=too-few-public-methods
        """Test double for partial S3 upload failure."""

        def __init__(self):
            self.calls = 0
            self.deleted = []

        async def upload_file(self, _path):
            self.calls += 1
            if self.calls == 1:
                return "stored/first.jpg"
            return None

        async def delete_file(self, object_key):
            self.deleted.append(object_key)
            return True

    photos = [_upload_file("first.jpg", b"abc"), _upload_file("second.png", b"def")]
    s3 = _FakeS3()

    monkeypatch.setattr(issues.aiofiles, "open", _AsyncFile)

    with pytest.raises(RuntimeError, match="Failed to upload photo: second.png"):
        asyncio.run(issues._upload_photos_to_s3(photos, s3))

    assert s3.deleted == ["stored/first.jpg"]


def test_get_issue_priority_options_returns_enum_values():
    """Test get issue priority options returns enum values."""
    response = asyncio.run(issues.get_issue_priority_options())

    assert response.priorities == ["LOW", "NORMAL", "HIGH"]


def test_create_issue_queues_auto_assignment(monkeypatch):
    """Test create issue schedules auto-assignment after returning."""

    class _FakeDB:
        """Track endpoint-level commits."""

        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.rollbacks += 1

    class _FakeIssueRepo:
        """Repository test double."""

        def __init__(self, _db):
            pass

        async def check_issue_label_exists(self, _issue_label):
            return False

        async def create_issue(self, issue_data, reporter_id, issue_label, attachment_paths):
            assert issue_data.issue_type == 1
            assert reporter_id == 41
            assert issue_label == "ISS-100"
            assert attachment_paths == ["stored/photo.jpg"]
            return type(
                "CreatedIssue",
                (),
                {
                    "issue_id": 17,
                    "issue_label": issue_label,
                    "status": "OPEN",
                    "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                },
            )()

    class _FakeCitizenRepo:
        """Citizen repository test double."""

        def __init__(self, _db):
            pass

        async def get_citizen_by_user_id(self, user_id):
            assert user_id == 7
            return type("CitizenProfile", (), {"citizen_id": 41})()

    async def _fake_upload(_photos):
        return ["stored/photo.jpg"], ["/tmp/photo.jpg"]

    async def _fake_delete(temp_paths):
        assert temp_paths == ["/tmp/photo.jpg"]

    monkeypatch.setattr(issues, "ensure_required_user_agent", lambda *_args: None)
    monkeypatch.setattr(issues, "validate_photos", lambda _photos: None)
    monkeypatch.setattr(issues, "_safe_upload_photos_to_s3", _fake_upload)
    monkeypatch.setattr(issues, "delete_temp_files", _fake_delete)
    monkeypatch.setattr(issues, "IssueRepository", _FakeIssueRepo)
    monkeypatch.setattr(issues, "CitizenRepository", _FakeCitizenRepo)
    monkeypatch.setattr(issues, "generate_issue_label", lambda: "ISS-100")
    monkeypatch.setattr(issues, "utc_to_timezone", lambda dt: dt.isoformat())

    db = _FakeDB()
    background_tasks = BackgroundTasks()
    response = asyncio.run(
        issues.create_issue(
            request=type("Request", (), {"headers": {"User-Agent": "BattinalaApp"}})(),
            background_tasks=background_tasks,
            photos=[],
            issue_create=ISSUE_CREATE_PAYLOAD,
            context=_issue_context(db, 7),
        )
    )

    assert response.issue_label == "ISS-100"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is issues.assign_issue_to_nearest_employee
    assert background_tasks.tasks[0].args == (17,)
    assert db.commits == 1
    assert db.rollbacks == 0


def test_create_issue_cleans_up_uploaded_files_when_commit_fails(monkeypatch):
    """Test create issue deletes uploaded files if the DB commit fails."""

    class _FakeDB:
        """Track commit failure handling."""

        def __init__(self):
            self.rollbacks = 0

        async def commit(self):
            raise RuntimeError("db down")

        async def rollback(self):
            self.rollbacks += 1

    class _FakeIssueRepo:
        """Repository test double."""

        def __init__(self, _db):
            pass

        async def check_issue_label_exists(self, _issue_label):
            return False

        async def create_issue(self, _issue_data, _reporter_id, issue_label, _attachment_paths):
            return type(
                "CreatedIssue",
                (),
                {
                    "issue_id": 17,
                    "issue_label": issue_label,
                    "status": "OPEN",
                    "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                },
            )()

    class _FakeCitizenRepo:
        """Citizen repository test double."""

        def __init__(self, _db):
            pass

        async def get_citizen_by_user_id(self, _user_id):
            return type("CitizenProfile", (), {"citizen_id": 41})()

    cleaned_up = []

    async def _fake_upload(_photos):
        return ["stored/photo.jpg"], ["/tmp/photo.jpg"]

    async def _fake_delete_temp(temp_paths):
        assert temp_paths == ["/tmp/photo.jpg"]

    async def _fake_delete_uploaded(object_keys):
        cleaned_up.append(list(object_keys))

    monkeypatch.setattr(issues, "ensure_required_user_agent", lambda *_args: None)
    monkeypatch.setattr(issues, "validate_photos", lambda _photos: None)
    monkeypatch.setattr(issues, "_safe_upload_photos_to_s3", _fake_upload)
    monkeypatch.setattr(issues, "delete_temp_files", _fake_delete_temp)
    monkeypatch.setattr(issues, "delete_uploaded_files", _fake_delete_uploaded)
    monkeypatch.setattr(issues, "IssueRepository", _FakeIssueRepo)
    monkeypatch.setattr(issues, "CitizenRepository", _FakeCitizenRepo)
    monkeypatch.setattr(issues, "generate_issue_label", lambda: "ISS-100")

    with pytest.raises(Exception) as exc:
        asyncio.run(
            issues.create_issue(
                request=type("Request", (), {"headers": {"User-Agent": "BattinalaApp"}})(),
                background_tasks=BackgroundTasks(),
                photos=[],
                issue_create=ISSUE_CREATE_PAYLOAD,
                context=_issue_context(_FakeDB(), 7),
            )
        )

    assert exc.value.status_code == 500
    assert cleaned_up == [["stored/photo.jpg"]]


def test_verify_issue_status_queues_auto_assignment_when_opened(monkeypatch):
    """Test verify issue schedules auto-assignment when opened."""

    class _FakeIssueRepo:
        """Repository test double."""

        def __init__(self, _db):
            self.issue = type(
                "Issue",
                (),
                {
                    "issue_id": 23,
                    "issue_label": "ISS-023",
                    "status": "PENDING_VERIFICATION",
                    "issue_type": 5,
                    "assignee_id": None,
                },
            )()

        async def get_issue_by_label(self, issue_label):
            assert issue_label == "ISS-023"
            return self.issue

        async def update_issue_status(self, issue, status):
            issue.status = status
            return issue

    class _FakeEmployeeRepo:
        """Repository test double."""

        def __init__(self, _db):
            pass

        async def get_employee_by_user_id(self, user_id):
            assert user_id == 11
            return type("Employee", (), {"department_id": 5})()

    monkeypatch.setattr(issues, "IssueRepository", _FakeIssueRepo)
    monkeypatch.setattr(issues, "EmployeeRepository", _FakeEmployeeRepo)

    background_tasks = BackgroundTasks()
    response = asyncio.run(
        issues.verify_issue_status(
            payload=IssueStatusUpdate(issue_label="ISS-023", status=IssueStatus.OPEN),
            background_tasks=background_tasks,
            db=object(),
            current_user=type("User", (), {"user_id": 11})(),
        )
    )

    assert response == {"message": "Issue status updated.", "status": IssueStatus.OPEN}
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is issues.assign_issue_to_nearest_employee
    assert background_tasks.tasks[0].args == (23,)
