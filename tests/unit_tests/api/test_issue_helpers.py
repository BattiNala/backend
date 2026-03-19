"""Tests for issue helpers."""

# pylint: disable=protected-access

import asyncio
from pathlib import Path

import pytest

from app.api.v1.endpoints import issues
from app.schemas.issue import IssueCreate


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
    payload = '{"issue_type": 1, "description": "Pothole", "latitude": 27.7, "longitude": 85.3}'

    parsed = issues._parse_issue_create(payload, IssueCreate)

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


def test_get_issue_priority_options_returns_enum_values():
    """Test get issue priority options returns enum values."""
    response = asyncio.run(issues.get_issue_priority_options())

    assert response.priorities == ["LOW", "NORMAL", "HIGH"]
