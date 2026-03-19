"""Tests for nearest node."""

import pytest

from app.routing.nearest_node import nearest_node_id, nearest_node_id_indexed
from app.routing.spatial_index import build_grid_index
from app.schemas.geo_location import GeoLocation


def test_nearest_node_id_returns_closest_node():
    """Test nearest node id returns closest node."""
    nodes = {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.8000, longitude=85.4000),
    }

    result = nearest_node_id(nodes, GeoLocation(latitude=27.7001, longitude=85.3001))

    assert result == 1


def test_nearest_node_id_raises_for_empty_nodes():
    """Test nearest node id raises for empty nodes."""
    with pytest.raises(ValueError, match="nodes is empty"):
        nearest_node_id({}, GeoLocation(latitude=27.7, longitude=85.3))


def test_nearest_node_id_indexed_delegates_to_grid_search():
    """Test nearest node id indexed delegates to grid search."""
    nodes = {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.7002, longitude=85.3002),
    }
    index = build_grid_index(nodes, cell_size_deg=0.001)

    result = nearest_node_id_indexed(index, GeoLocation(latitude=27.70015, longitude=85.30015))

    assert result == 2
