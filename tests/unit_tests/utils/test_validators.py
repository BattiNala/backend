"""Tests for validators."""

from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers
from starlette.requests import Request

from app.utils.validators import ensure_required_user_agent, validate_photos


def _request(user_agent: str | None) -> Request:
    """Request."""
    headers = []
    if user_agent is not None:
        headers.append((b"user-agent", user_agent.encode()))
    return Request({"type": "http", "headers": headers})


def _upload_file(content_type: str) -> UploadFile:
    """Upload file."""
    return UploadFile(
        file=BytesIO(b"image-data"),
        filename="photo.jpg",
        headers=Headers({"content-type": content_type}),
    )


def test_ensure_required_user_agent_accepts_matching_device_type():
    """Test ensure required user agent accepts matching device type."""
    ensure_required_user_agent(_request("BattinalaApp/1.0"), "BattinalaApp")


def test_ensure_required_user_agent_rejects_missing_or_wrong_agent():
    """Test ensure required user agent rejects missing or wrong agent."""
    with pytest.raises(Exception) as missing_exc:
        ensure_required_user_agent(_request(None), "browser")
    assert missing_exc.value.status_code == 400

    with pytest.raises(Exception) as wrong_exc:
        ensure_required_user_agent(_request("Mozilla/5.0"), "BattinalaApp")
    assert wrong_exc.value.status_code == 400


def test_validate_photos_rejects_empty_and_invalid_types():
    """Test validate photos rejects empty and invalid types."""
    with pytest.raises(Exception) as empty_exc:
        validate_photos([])
    assert empty_exc.value.status_code == 400

    with pytest.raises(Exception) as invalid_exc:
        validate_photos([_upload_file("application/pdf")])
    assert invalid_exc.value.status_code == 400


def test_validate_photos_accepts_allowed_types():
    """Test validate photos accepts allowed types."""
    validate_photos(
        [_upload_file("image/jpeg"), _upload_file("image/png"), _upload_file("image/webp")]
    )
