"""Tests for spatial index."""

import pytest

from app.routing.spatial_index import _iter_cell_keys, build_grid_index, nearest_node_id_grid
from app.schemas.geo_location import GeoLocation


def test_build_grid_index_buckets_nodes_into_cells():
    """Test build grid index buckets nodes into cells."""
    nodes = {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.7004, longitude=85.3004),
    }

    index = build_grid_index(nodes, cell_size_deg=0.001)

    assert index.cell_key(nodes[1]) in index.cells
    assert index.cells[index.cell_key(nodes[1])] == [1]
    assert index.cells[index.cell_key(nodes[2])] == [2]


def test_nearest_node_id_grid_raises_when_no_candidates_found():
    """Test nearest node id grid raises when no candidates found."""
    index = build_grid_index({}, cell_size_deg=0.001)

    with pytest.raises(ValueError, match="No nodes found within max_radius_cells"):
        nearest_node_id_grid(
            index,
            GeoLocation(latitude=27.7, longitude=85.3),
            max_radius_cells=0,
        )


def test_iter_cell_keys_returns_ring_for_radius_one():
    """Test iter cell keys returns ring for radius one."""
    keys = list(_iter_cell_keys((0, 0), 1))

    assert len(keys) == 8
    assert (0, 0) not in keys
