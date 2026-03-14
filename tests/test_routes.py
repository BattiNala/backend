# pylint: disable=missing-module-docstring

import pytest

from app.api.v1.endpoints import routes
from app.routing.astar import AStarResult
from app.schemas.geo_location import GeoLocation
from app.schemas.route import RouteRequest
from app.services.route_service import SnappedLocation

pytest.importorskip("fastapi")


class _StubRouteService:
    """A stub RouteService for testing the shortest-route endpoint."""

    def nearest_node(self, location: GeoLocation) -> SnappedLocation:
        """Return a dummy snapped location for testing."""
        return SnappedLocation(node_id=1, location=location, distance_m=0.0)

    def shortest_path_between_nodes(self, start_id: int = 1, goal_id: int = 2) -> AStarResult:
        """Return a dummy A* result for testing"""
        return AStarResult(path=[start_id, goal_id], distance_km=1.25)

    def path_to_locations(self, _result: AStarResult) -> list[GeoLocation]:
        """Return a dummy path of GeoLocations for testing."""
        return [
            GeoLocation(latitude=27.7000, longitude=85.3000),
            GeoLocation(latitude=27.7100, longitude=85.3100),
        ]

    def simplify_path(
        self,
        path: list[GeoLocation],
        *,
        _tolerance_m: float,
        _preserve_indices: set[int] | None = None,
    ) -> list[GeoLocation]:
        """Return the input path unchanged for testing."""
        return path


def test_shortest_route(monkeypatch):
    """Test the shortest-route endpoint returns the current response schema."""
    monkeypatch.setattr(routes, "_route_service", _StubRouteService())
    response = routes.shortest_route(
        RouteRequest(
            start=GeoLocation(latitude=27.7000, longitude=85.3000),
            destination=GeoLocation(latitude=27.7100, longitude=85.3100),
        )
    )

    assert response.model_dump() == {
        "distance_km": 1.25,
        "path": [
            {"latitude": 27.7, "longitude": 85.3},
            {"latitude": 27.71, "longitude": 85.31},
        ],
        "snapped_start": {"latitude": 27.7, "longitude": 85.3},
        "snapped_destination": {"latitude": 27.71, "longitude": 85.31},
    }
