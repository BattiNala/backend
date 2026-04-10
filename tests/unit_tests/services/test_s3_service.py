"""Tests for s3 service."""

# pylint: disable=duplicate-code

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.s3_service import S3Config, S3Service


class _FakeBody:
    """Test double for FakeBody."""

    def __init__(self, chunks):
        """Init."""
        self._chunks = list(chunks)
        self.closed = False

    async def read(self, _size):
        """Read."""
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    async def close(self):
        """Close."""
        self.closed = True


class _FakeBodyWithSyncClose:
    """Test double with a synchronous close method."""

    def __init__(self, chunks):
        """Init."""
        self._chunks = list(chunks)
        self.closed = False

    async def read(self, _size):
        """Read."""
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    def close(self):
        """Close."""
        self.closed = True


class _FakeClient:
    """Test double for FakeClient."""

    def __init__(self):
        """Init."""
        self.put_calls = []
        self.deleted = []
        self.list_calls = 0

    async def put_object(self, **kwargs):
        """Put object."""
        self.put_calls.append(kwargs)

    async def get_object(self, **_kwargs):
        """Get object."""
        return {"Body": _FakeBody([b"hello ", b"world"])}

    async def delete_object(self, **kwargs):
        """Delete object."""
        self.deleted.append(kwargs)

    async def list_objects_v2(self, **_kwargs):
        """List objects v2."""
        self.list_calls += 1
        if self.list_calls == 1:
            return {
                "Contents": [{"Key": "images/1.png"}],
                "IsTruncated": True,
                "NextContinuationToken": "next",
            }
        return {"Contents": [{"Key": "images/2.png"}], "IsTruncated": False}

    async def generate_presigned_url(self, _operation, **kwargs):
        """Generate presigned url."""
        return f"https://example.com/{kwargs['Params']['Key']}?expires={kwargs['ExpiresIn']}"


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

    async def read(self):
        """Read."""
        return self.path.read_bytes()

    async def write(self, data):
        """Write."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(data)


class _FakeClientSyncClose(_FakeClient):
    """Test client returning a body with sync close semantics."""

    async def get_object(self, **_kwargs):
        """Get object."""
        return {"Body": _FakeBodyWithSyncClose([b"sync ", b"close"])}


def test_build_s3_url_supports_aws_and_custom_endpoints():
    """Test build s3 url supports aws and custom endpoints."""
    aws_service = S3Service(
        S3Config(bucket_name="bucket", region_name="us-east-1", endpoint_url=None)
    )
    path_service = S3Service(
        S3Config(
            bucket_name="bucket",
            region_name="auto",
            endpoint_url="https://storage.example.com",
            force_path_style=True,
        )
    )
    virtual_service = S3Service(
        S3Config(
            bucket_name="bucket",
            region_name="auto",
            endpoint_url="https://storage.example.com",
            force_path_style=False,
        )
    )

    assert (
        aws_service.build_s3_url("a/b.png") == "https://bucket.s3.us-east-1.amazonaws.com/a/b.png"
    )
    assert path_service.build_s3_url("/a/b.png") == "https://storage.example.com/bucket/a/b.png"
    assert virtual_service.build_s3_url("a/b.png") == "https://bucket.storage.example.com/a/b.png"


def test_s3_methods_raise_when_client_is_not_initialized(tmp_path):
    """Test s3 methods raise when client is not initialized."""
    service = S3Service(S3Config(bucket_name="bucket"))

    with pytest.raises(RuntimeError):
        asyncio.run(service.upload_file(tmp_path / "x.txt"))

    with pytest.raises(RuntimeError):
        asyncio.run(service.download_file("key", tmp_path / "x.txt"))


def test_upload_download_delete_list_and_presign(monkeypatch, tmp_path):
    """Test upload download delete list and presign."""
    service = S3Service(S3Config(bucket_name="bucket"))
    service.client = _FakeClient()
    file_path = tmp_path / "photo.png"
    file_path.write_bytes(b"payload")

    class _FrozenDateTime:  # pylint: disable=too-few-public-methods
        """Test double for FrozenDateTime."""

        @staticmethod
        def now(_tz):
            """Now."""
            return datetime(2024, 1, 2, tzinfo=timezone.utc)

    monkeypatch.setattr("app.services.s3_service.datetime", _FrozenDateTime)

    def _uuid():
        """Return a deterministic UUID-like object."""
        return type("UUID", (), {"hex": "abc123"})()

    monkeypatch.setattr("app.services.s3_service.uuid4", _uuid)
    monkeypatch.setattr("app.services.s3_service.aiofiles.open", _AsyncFile)

    object_key = asyncio.run(service.upload_file(file_path))
    download_path = tmp_path / "downloads" / "photo.png"
    downloaded = asyncio.run(service.download_file(object_key, download_path))
    deleted = asyncio.run(service.delete_file(object_key))
    keys = asyncio.run(service.list_files(prefix="images/"))
    presigned = asyncio.run(service.presign_get(object_key, expiration=60))

    assert object_key == "images/2024/01/abc123.png"
    assert service.client.put_calls[0]["Body"] == b"payload"
    assert downloaded is True
    assert download_path.read_bytes() == b"hello world"
    assert deleted is True
    assert keys == ["images/1.png", "images/2.png"]
    assert presigned == "https://example.com/images/2024/01/abc123.png?expires=60"


def test_download_file_supports_sync_stream_close(monkeypatch, tmp_path):
    """Download should tolerate providers that expose a sync close method."""
    service = S3Service(S3Config(bucket_name="bucket"))
    service.client = _FakeClientSyncClose()
    download_path = tmp_path / "downloads" / "photo.png"

    monkeypatch.setattr("app.services.s3_service.aiofiles.open", _AsyncFile)

    downloaded = asyncio.run(service.download_file("images/key.png", download_path))

    assert downloaded is True
    assert download_path.read_bytes() == b"sync close"
