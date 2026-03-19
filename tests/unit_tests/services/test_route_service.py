"""Tests for route service."""

# pylint: disable=protected-access

import pickle

from app.routing.astar import AStarResult
from app.routing.graph_builder import Graph
from app.schemas.geo_location import GeoLocation
from app.services import route_service as route_service_module
from app.services.route_service import RouteService, SnappedLocation


def _graph():
    """Graph."""
    nodes = {
        1: GeoLocation(latitude=27.7000, longitude=85.3000),
        2: GeoLocation(latitude=27.7005, longitude=85.3005),
    }
    return Graph(
        nodes=nodes,
        edges={1: [2], 2: [1]},
        edges_weighted={1: [(2, 1.0)], 2: [(1, 1.0)]},
        reverse_edges_weighted={1: [(2, 1.0)], 2: [(1, 1.0)]},
    )


def test_shortest_path_and_location_helpers_delegate_to_graph(monkeypatch, tmp_path):
    """Test shortest path and location helpers delegate to graph."""
    service = RouteService(pbf_path=tmp_path / "map.pbf")
    graph = _graph()
    service._graph = graph
    service._index = object()

    monkeypatch.setattr(
        route_service_module,
        "astar_shortest_path",
        lambda *args, **kwargs: AStarResult(path=[1, 2], distance_km=1.0),
    )
    monkeypatch.setattr(route_service_module, "nearest_node_id_indexed", lambda index, location: 2)

    result = service.shortest_path_between_nodes(1, 2)
    snapped = service.nearest_node(GeoLocation(latitude=27.7005, longitude=85.3005))

    assert result == AStarResult(path=[1, 2], distance_km=1.0)
    assert service.path_to_locations(result) == [graph.nodes[1], graph.nodes[2]]
    assert snapped == SnappedLocation(node_id=2, location=graph.nodes[2], distance_m=0.0)


def test_shortest_path_and_snapped_locations_use_nearest_node(monkeypatch, tmp_path):
    """Test shortest path and snapped locations use nearest node."""
    service = RouteService(pbf_path=tmp_path / "map.pbf")
    start = GeoLocation(latitude=27.7, longitude=85.3)
    end = GeoLocation(latitude=27.8, longitude=85.4)
    calls = []

    def fake_nearest(location):
        """Fake nearest."""
        calls.append(location)
        node_id = 1 if len(calls) == 1 else 2
        return SnappedLocation(node_id=node_id, location=location, distance_m=3.0)

    monkeypatch.setattr(service, "nearest_node", fake_nearest)
    monkeypatch.setattr(
        service,
        "shortest_path_between_nodes",
        lambda start_id, goal_id: AStarResult(path=[start_id, goal_id], distance_km=2.5),
    )

    result = service.shortest_path(start, end)
    snapped_start, snapped_end = service.snapped_locations(start, end)
    snapped = service.snapped_locations_with_distance(start, end)

    assert result == AStarResult(path=[1, 2], distance_km=2.5)
    assert snapped_start == start
    assert snapped_end == end
    assert snapped == (start, 3.0, end, 3.0)


def test_load_or_build_graph_reads_cached_payload(tmp_path):
    """Test load or build graph reads cached payload."""
    pbf_path = tmp_path / "map.pbf"
    pbf_path.write_bytes(b"pbf")
    cache_path = tmp_path / "route_graph_cache.pkl"
    cache_payload = {
        "pbf_mtime": pbf_path.stat().st_mtime,
        "nodes": {1: (27.7, 85.3), 2: (27.8, 85.4)},
        "edges_weighted": {1: [(2, 1.2)]},
    }
    cache_path.write_bytes(pickle.dumps(cache_payload))

    service = RouteService(pbf_path=pbf_path)
    service._cache_path = cache_path

    graph = service._load_or_build_graph()

    assert graph.nodes[1] == GeoLocation(latitude=27.7, longitude=85.3)
    assert graph.edges_weighted == {1: [(2, 1.2)]}
    assert graph.reverse_edges_weighted == {2: [(1, 1.2)]}


def test_load_or_build_graph_rebuilds_and_persists_cache(monkeypatch, tmp_path):
    """Test load or build graph rebuilds and persists cache."""
    pbf_path = tmp_path / "map.pbf"
    pbf_path.write_bytes(b"pbf")
    cache_path = tmp_path / "route_graph_cache.pkl"
    graph = _graph()
    ways = [type("WayObj", (), {"nodes": [1, 2], "oneway": False})()]

    monkeypatch.setattr(
        route_service_module,
        "load_osm_pbf",
        lambda path, allowed_highways: (graph.nodes, ways),
    )
    monkeypatch.setattr(
        route_service_module,
        "build_graph_from_ways",
        lambda nodes, way_data, bidirectional: graph,
    )

    service = RouteService(pbf_path=pbf_path)
    service._cache_path = cache_path

    rebuilt = service._load_or_build_graph()

    assert rebuilt == graph
    assert cache_path.exists()


def test_build_reverse_edges_inverts_weighted_adjacency():
    """Test build reverse edges inverts weighted adjacency."""
    reverse = RouteService._build_reverse_edges({1: [(2, 1.0)], 2: [(3, 2.0)]})

    assert reverse == {2: [(1, 1.0)], 3: [(2, 2.0)]}
