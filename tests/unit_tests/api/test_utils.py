"""Tests for utils."""

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1.utils import with_db_error


def test_with_db_error_returns_result():
    """Test with db error returns result."""

    async def action():
        """Action."""
        return "ok"

    assert asyncio.run(with_db_error(action)) == "ok"


def test_with_db_error_preserves_http_exception():
    """Test with db error preserves http exception."""

    async def action():
        """Action."""
        raise HTTPException(status_code=404, detail="missing")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(with_db_error(action))

    assert exc.value.status_code == 404


def test_with_db_error_wraps_unexpected_exceptions():
    """Test with db error wraps unexpected exceptions."""

    async def action():
        """Action."""
        raise RuntimeError("db blew up")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(with_db_error(action))

    assert exc.value.status_code == 500
    assert exc.value.detail == "db blew up"
