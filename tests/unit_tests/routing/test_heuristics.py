"""Tests for heuristics."""

import pytest

from app.routing.heuristics import haversine_heuristic
from app.schemas.geo_location import GeoLocation


def test_haversine_heuristic_returns_distance_to_goal():
    """Test haversine heuristic returns distance to goal."""
    nodes = {
        1: GeoLocation(latitude=27.7, longitude=85.3),
        2: GeoLocation(latitude=27.71, longitude=85.31),
    }

    heuristic = haversine_heuristic(nodes, 2)

    assert heuristic(2) == pytest.approx(0.0)
    assert heuristic(1) > 0.0
