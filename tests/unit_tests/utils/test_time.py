"""Tests for time."""

from datetime import datetime

from app.utils.time import utc_to_timezone


def test_utc_to_timezone_accepts_datetime_and_string_inputs():
    """Test utc to timezone accepts datetime and string inputs."""
    expected = utc_to_timezone(datetime(2024, 1, 1, 0, 0, 0), "Asia/Kathmandu")
    actual = utc_to_timezone("2024-01-01T00:00:00", "Asia/Kathmandu")

    assert expected == actual
    assert (actual.hour, actual.minute) == (5, 45)
