"""Tests for astar."""

# pylint: disable=duplicate-code

import pytest

from app.routing.astar import (
    AStarConfig,
    _reconstruct_bidirectional_path,
    _reconstruct_path,
    _unpack_edge,
    astar_shortest_path,
)
from app.schemas.geo_location import GeoLocation


def _nodes():
    """Nodes."""
    return {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.7005, longitude=85.3010),
        3: GeoLocation(latitude=27.7010, longitude=85.3020),
        4: GeoLocation(latitude=27.7015, longitude=85.3030),
    }


def test_reconstruct_helpers_build_expected_paths():
    """Test reconstruct helpers build expected paths."""
    assert _reconstruct_path({2: 1, 3: 2}, 3) == [1, 2, 3]
    assert _reconstruct_bidirectional_path({2: 1}, {3: 4}, 2) == [1, 2]


def test_unpack_edge_supports_bare_nodes_and_weighted_edges():
    """Test unpack edge supports bare nodes and weighted edges."""
    nodes = _nodes()

    assert _unpack_edge(2, nodes, 1, lambda a, b: 7.5) == (2, 7.5)
    assert _unpack_edge((2, 1.25), nodes, 1, lambda a, b: 7.5) == (2, 1.25)
    assert _unpack_edge(99, nodes, 1, lambda a, b: 7.5) == (None, 0.0)


def test_astar_shortest_path_supports_single_direction_graphs():
    """Test astar shortest path supports single direction graphs."""
    result = astar_shortest_path(
        _nodes(),
        {1: [2], 2: [3], 3: [4]},
        1,
        4,
    )

    assert result is not None
    assert result.path == [1, 2, 3, 4]


def test_astar_shortest_path_respects_max_expansions():
    """Test astar shortest path respects max expansions."""
    result = astar_shortest_path(
        _nodes(),
        {1: [2], 2: [3], 3: [4]},
        1,
        4,
        config=AStarConfig(max_expansions=1),
    )

    assert result is None


def test_astar_shortest_path_uses_bidirectional_search_when_reverse_edges_exist():
    """Test astar shortest path uses bidirectional search when reverse edges exist."""
    edges = {1: [(2, 1.0), (4, 10.0)], 2: [(3, 1.0)], 3: [(4, 1.0)]}
    reverse_edges = {2: [(1, 1.0)], 3: [(2, 1.0)], 4: [(1, 10.0), (3, 1.0)]}

    result = astar_shortest_path(
        _nodes(),
        edges,
        1,
        4,
        config=AStarConfig(reverse_edges=reverse_edges),
    )

    assert result is not None
    assert result.path == [1, 2, 3, 4]
    assert result.distance_km == 3.0


def test_astar_shortest_path_raises_for_unknown_nodes():
    """Test astar shortest path raises for unknown nodes."""
    with pytest.raises(ValueError, match="start_id and goal_id must exist in nodes"):
        astar_shortest_path(_nodes(), {}, 1, 99)
