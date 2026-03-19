"""Tests for graph builder."""

from app.routing.graph_builder import _iter_way_nodes, build_graph_from_ways
from app.schemas.geo_location import GeoLocation


def test_iter_way_nodes_normalizes_plain_and_tuple_inputs():
    """Test iter way nodes normalizes plain and tuple inputs."""
    assert _iter_way_nodes([1, 2, 3]) == ([1, 2, 3], False)
    assert _iter_way_nodes(([1, 2, 3], True)) == ([1, 2, 3], True)


def test_build_graph_from_ways_respects_oneway_and_skips_missing_nodes():
    """Test build graph from ways respects oneway and skips missing nodes."""
    nodes = {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.7005, longitude=85.3005),
        3: GeoLocation(latitude=27.7010, longitude=85.3010),
    }

    graph = build_graph_from_ways(
        nodes,
        [
            ([1, 2, 3], False),
            ([3, 99, 1], True),
        ],
        bidirectional=True,
    )

    assert graph.edges[1] == [2]
    assert sorted(graph.edges[2]) == [1, 3]
    assert 1 not in graph.edges.get(3, [])
    assert graph.reverse_edges_weighted[2][0][0] == 1
