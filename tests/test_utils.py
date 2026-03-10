# pylint: disable=missing-module-docstring

from datetime import datetime

import pytest

from app.algorithms.haversine import haversine
from app.schemas.geo_location import GeoLocation
from app.utils.time import utc_to_timezone


def test_haversine_zero_distance():
    """Test that the distance between two identical points is zero."""
    loc = GeoLocation(latitude=0.0, longitude=0.0)

    assert haversine(loc, loc) == pytest.approx(0.0)


def test_haversine_one_degree_at_equator():
    """
    Test that the distance for 1 degree of longitude
    at the equator is approximately 111.195 km.
    """
    loc1 = GeoLocation(latitude=0.0, longitude=0.0)
    loc2 = GeoLocation(latitude=0.0, longitude=1.0)

    # ~111.195 km for 1 degree of longitude at the equator
    assert haversine(loc1, loc2) == pytest.approx(111.195, rel=1e-3)


def test_utc_to_timezone_from_datetime():
    """Test converting UTC datetime to local timezone datetime."""
    utc_dt = datetime(2024, 1, 1, 0, 0, 0)

    local_dt = utc_to_timezone(utc_dt, "Asia/Kathmandu")

    assert local_dt.tzinfo is not None
    assert local_dt.tzinfo.key == "Asia/Kathmandu"
    assert (local_dt.hour, local_dt.minute) == (5, 45)


def test_utc_to_timezone_from_iso_string():
    """Test converting UTC ISO string to local timezone datetime."""
    local_dt = utc_to_timezone("2024-01-01T00:00:00", "Asia/Kathmandu")

    assert local_dt.tzinfo is not None
    assert local_dt.tzinfo.key == "Asia/Kathmandu"
    assert (local_dt.hour, local_dt.minute) == (5, 45)
