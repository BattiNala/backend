"""Tests for routes endpoint."""

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import routes
from app.routing.astar import AStarResult
from app.schemas.geo_location import GeoLocation
from app.schemas.route import RouteRequest
from app.services.route_service import SnappedLocation


class _StubRouteService:
    """Test double for StubRouteService."""

    # pylint: disable=too-many-arguments
    def __init__(self, *, result, path, snapped_start, snapped_destination, should_raise=False):
        """Init."""
        self._result = result
        self._path = list(path)
        self._snapped_start = snapped_start
        self._snapped_destination = snapped_destination
        self._should_raise = should_raise

    def nearest_node(self, location):
        """Nearest node."""
        if self._should_raise:
            raise ValueError("bad location")
        if location == START:
            return self._snapped_start
        return self._snapped_destination

    def shortest_path_between_nodes(self, _start_id, _goal_id):
        """Shortest path between nodes."""
        return self._result

    def path_to_locations(self, _result):
        """Path to locations."""
        return list(self._path)

    def simplify_path(self, path, *, tolerance_m, preserve_indices):
        """Simplify path."""
        assert tolerance_m == routes.settings.ROUTE_RESPONSE_SIMPLIFY_TOLERANCE_M
        assert preserve_indices
        return path


START = GeoLocation(latitude=27.7000, longitude=85.3000)
DESTINATION = GeoLocation(latitude=27.7100, longitude=85.3100)


def test_shortest_route_returns_augmented_path_for_large_snap_distance(monkeypatch):
    """Test shortest route returns augmented path for large snap distance."""
    monkeypatch.setattr(routes.settings, "ROUTE_MAX_SNAP_DISTANCE_M", 5.0, raising=False)
    monkeypatch.setattr(
        routes.settings,
        "ROUTE_RESPONSE_SIMPLIFY_TOLERANCE_M",
        7.5,
        raising=False,
    )
    service = _StubRouteService(
        result=AStarResult(path=[1, 2], distance_km=1.25),
        path=[GeoLocation(latitude=27.7050, longitude=85.3050)],
        snapped_start=SnappedLocation(node_id=1, location=START, distance_m=10.0),
        snapped_destination=SnappedLocation(
            node_id=2,
            location=DESTINATION,
            distance_m=12.0,
        ),
    )
    monkeypatch.setattr(routes, "_route_service", service)

    response = routes.shortest_route(RouteRequest(start=START, destination=DESTINATION))

    assert response.distance_km == 1.25
    assert response.path == [START, GeoLocation(latitude=27.7050, longitude=85.3050), DESTINATION]


def test_shortest_route_raises_404_when_no_route_found(monkeypatch):
    """Test shortest route raises 404 when no route found."""
    service = _StubRouteService(
        result=None,
        path=[],
        snapped_start=SnappedLocation(node_id=1, location=START, distance_m=1.0),
        snapped_destination=SnappedLocation(node_id=2, location=DESTINATION, distance_m=1.0),
    )
    monkeypatch.setattr(routes, "_route_service", service)

    with pytest.raises(HTTPException) as exc:
        routes.shortest_route(RouteRequest(start=START, destination=DESTINATION))

    assert exc.value.status_code == 404


def test_shortest_route_raises_400_for_invalid_snap(monkeypatch):
    """Test shortest route raises 400 for invalid snap."""
    service = _StubRouteService(
        result=None,
        path=[],
        snapped_start=SnappedLocation(node_id=1, location=START, distance_m=1.0),
        snapped_destination=SnappedLocation(node_id=2, location=DESTINATION, distance_m=1.0),
        should_raise=True,
    )
    monkeypatch.setattr(routes, "_route_service", service)

    with pytest.raises(HTTPException) as exc:
        routes.shortest_route(RouteRequest(start=START, destination=DESTINATION))

    assert exc.value.status_code == 400
