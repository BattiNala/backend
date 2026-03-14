"""Tests for path simplification helpers."""

from app.routing.path_simplify import simplify_path
from app.schemas.geo_location import GeoLocation


def test_simplify_path_removes_redundant_straight_points():
    """Remove near-collinear points when tolerance allows."""
    path = [
        GeoLocation(latitude=27.700000, longitude=85.300000),
        GeoLocation(latitude=27.700010, longitude=85.300100),
        GeoLocation(latitude=27.700020, longitude=85.300200),
        GeoLocation(latitude=27.700030, longitude=85.300300),
    ]

    simplified = simplify_path(path, tolerance_m=5.0)

    assert simplified == [path[0], path[-1]]


def test_simplify_path_preserves_snap_transition_points():
    """Keep explicit indices even when simplifying."""
    path = [
        GeoLocation(latitude=27.696600, longitude=85.359100),
        GeoLocation(latitude=27.696829, longitude=85.3592589),
        GeoLocation(latitude=27.696900, longitude=85.359700),
        GeoLocation(latitude=27.697000, longitude=85.360200),
        GeoLocation(latitude=27.698700, longitude=85.318500),
    ]

    simplified = simplify_path(path, tolerance_m=50.0, preserve_indices={1, len(path) - 2})

    assert simplified[0] == path[0]
    assert path[1] in simplified
    assert path[-2] in simplified
    assert simplified[-1] == path[-1]
