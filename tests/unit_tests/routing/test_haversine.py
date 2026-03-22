"""Tests for haversine."""

import pytest

from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation


def test_haversine_returns_zero_for_identical_points():
    """Test haversine returns zero for identical points."""
    loc = GeoLocation(latitude=0.0, longitude=0.0)

    assert haversine(loc, loc) == pytest.approx(0.0)


def test_haversine_matches_expected_equator_distance():
    """Test haversine matches expected equator distance."""
    start = GeoLocation(latitude=0.0, longitude=0.0)
    end = GeoLocation(latitude=0.0, longitude=1.0)

    assert haversine(start, end) == pytest.approx(111.195, rel=1e-3)
