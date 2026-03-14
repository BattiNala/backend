"""Tests for A* routing helpers."""

from app.routing.astar import AStarConfig, astar_shortest_path
from app.schemas.geo_location import GeoLocation


def test_astar_shortest_path_uses_reverse_edges_for_directed_graph():
    """Prefer the cheaper directed path when reverse edges are provided."""
    nodes = {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.7005, longitude=85.3010),
        3: GeoLocation(latitude=27.7010, longitude=85.3020),
        4: GeoLocation(latitude=27.7015, longitude=85.3030),
    }
    edges = {
        1: [(2, 1.0), (4, 10.0)],
        2: [(3, 1.0)],
        3: [(4, 1.0)],
    }
    reverse_edges = {
        2: [(1, 1.0)],
        3: [(2, 1.0)],
        4: [(1, 10.0), (3, 1.0)],
    }

    result = astar_shortest_path(
        nodes,
        edges,
        1,
        4,
        config=AStarConfig(reverse_edges=reverse_edges),
    )

    assert result is not None
    assert result.path == [1, 2, 3, 4]
    assert result.distance_km == 3.0


def test_astar_shortest_path_handles_same_start_and_goal():
    """Return a trivial path when start and goal are identical."""
    nodes = {1: GeoLocation(latitude=27.7000, longitude=85.3000)}

    result = astar_shortest_path(nodes, {}, 1, 1, config=AStarConfig(reverse_edges={}))

    assert result is not None
    assert result.path == [1]
    assert result.distance_km == 0.0
