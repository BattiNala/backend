"""Tests for path simplify."""

import pytest

from app.routing.path_simplify import _point_to_segment_distance_m, _project_m, simplify_path
from app.schemas.geo_location import GeoLocation


def test_simplify_path_keeps_endpoints_and_preserved_indices():
    """Test simplify path keeps endpoints and preserved indices."""
    path = [
        GeoLocation(latitude=27.696600, longitude=85.359100),
        GeoLocation(latitude=27.696829, longitude=85.359259),
        GeoLocation(latitude=27.696900, longitude=85.359700),
        GeoLocation(latitude=27.697000, longitude=85.360200),
        GeoLocation(latitude=27.698700, longitude=85.318500),
    ]

    simplified = simplify_path(path, tolerance_m=50.0, preserve_indices={1, 3})

    assert simplified[0] == path[0]
    assert path[1] in simplified
    assert path[3] in simplified
    assert simplified[-1] == path[-1]


def test_point_to_segment_distance_handles_zero_length_segment():
    """Test point to segment distance handles zero length segment."""
    point = GeoLocation(latitude=27.7001, longitude=85.3001)
    start = GeoLocation(latitude=27.7000, longitude=85.3000)

    distance = _point_to_segment_distance_m(point, start, start)

    assert distance > 0.0


def test_project_m_returns_origin_as_zero_vector():
    """Test project m returns origin as zero vector."""
    origin = GeoLocation(latitude=27.7, longitude=85.3)

    assert _project_m(origin, origin) == pytest.approx((0.0, 0.0))
