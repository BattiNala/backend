"""Tests for health."""

import pytest

from app.main import health

pytest.importorskip("fastapi")


def test_health_ok():
    """Test that the health endpoint returns the expected status."""
    assert health() == {"status": "ok"}
