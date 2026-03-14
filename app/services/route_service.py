"""Route planning service using A* over an OSM graph."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.routing.astar import AStarConfig, AStarResult, astar_shortest_path
from app.routing.graph_builder import Graph, build_graph_from_ways
from app.routing.haversine import haversine
from app.routing.nearest_node import nearest_node_id_indexed
from app.routing.osm_pbf_loader import load_osm_pbf
from app.routing.path_simplify import simplify_path
from app.routing.spatial_index import GridIndex, build_grid_index
from app.schemas.geo_location import GeoLocation


@dataclass(frozen=True, slots=True)
class SnappedLocation:
    """Nearest graph node and snap distance for a request location."""

    node_id: int
    location: GeoLocation
    distance_m: float


@dataclass
class RouteService:
    """Route planner that loads an OSM-derived graph on demand and reuses it."""

    pbf_path: Path
    grid_cell_size_deg: float = 0.005
    _graph: Optional[Graph] = None
    _index: Optional[GridIndex] = None
    _cache_path: Optional[Path] = None

    def ensure_loaded(self) -> None:
        """Load the graph and nearest-node index once for this service instance."""
        if self._graph is not None and self._index is not None:
            return

        graph = self._load_or_build_graph()
        index = build_grid_index(graph.nodes, cell_size_deg=self.grid_cell_size_deg)

        self._graph = graph
        self._index = index

    def shortest_path(self, start: GeoLocation, destination: GeoLocation) -> AStarResult | None:
        """Snap raw coordinates to the graph and route between those snapped nodes."""
        snapped_start = self.nearest_node(start)
        snapped_destination = self.nearest_node(destination)
        return self.shortest_path_between_nodes(snapped_start.node_id, snapped_destination.node_id)

    def shortest_path_between_nodes(self, start_id: int, goal_id: int) -> AStarResult | None:
        """Run shortest-path search between two already-snapped graph node ids."""
        self.ensure_loaded()
        assert self._graph is not None

        edges = self._graph.edges_weighted or self._graph.edges
        return astar_shortest_path(
            self._graph.nodes,
            edges,
            start_id,
            goal_id,
            config=AStarConfig(reverse_edges=self._graph.reverse_edges_weighted),
        )

    def path_to_locations(self, result: AStarResult) -> list[GeoLocation]:
        """Convert a node-id path returned by A* into response coordinates."""
        self.ensure_loaded()
        assert self._graph is not None
        return [self._graph.nodes[node_id] for node_id in result.path]

    def simplify_path(
        self,
        path: list[GeoLocation],
        *,
        tolerance_m: float,
        preserve_indices: set[int] | None = None,
    ) -> list[GeoLocation]:
        """Simplify response geometry while preserving important transition points."""
        return simplify_path(path, tolerance_m=tolerance_m, preserve_indices=preserve_indices)

    def snapped_locations(
        self, start: GeoLocation, destination: GeoLocation
    ) -> tuple[GeoLocation, GeoLocation]:
        """Return the nearest routable graph locations for start and destination."""
        snapped_start = self.nearest_node(start)
        snapped_destination = self.nearest_node(destination)
        return snapped_start.location, snapped_destination.location

    def snapped_locations_with_distance(
        self, start: GeoLocation, destination: GeoLocation
    ) -> tuple[GeoLocation, float, GeoLocation, float]:
        """Return snapped graph locations together with their snap distances in meters."""
        snapped_start = self.nearest_node(start)
        snapped_destination = self.nearest_node(destination)
        return (
            snapped_start.location,
            snapped_start.distance_m,
            snapped_destination.location,
            snapped_destination.distance_m,
        )

    def nearest_node(self, location: GeoLocation) -> SnappedLocation:
        """Find the nearest routable graph node to an arbitrary coordinate."""
        self.ensure_loaded()
        assert self._graph is not None and self._index is not None

        node_id = nearest_node_id_indexed(self._index, location)
        node_loc = self._graph.nodes[node_id]
        distance_m = haversine(location, node_loc) * 1000.0
        return SnappedLocation(node_id=node_id, location=node_loc, distance_m=distance_m)

    def _load_or_build_graph(self) -> Graph:
        """Load the serialized graph cache or build it from the configured OSM file."""
        cache_path = self._cache_path or Path(settings.ROUTE_GRAPH_CACHE_PATH)
        pbf_mtime = self.pbf_path.stat().st_mtime
        if cache_path.exists():
            try:
                with cache_path.open("rb") as f:
                    cached = pickle.load(f)
                if cached.get("pbf_mtime") == pbf_mtime:
                    nodes = {
                        node_id: GeoLocation(latitude=lat, longitude=lon)
                        for node_id, (lat, lon) in cached["nodes"].items()
                    }
                    edges_weighted = cached["edges_weighted"]
                    reverse_edges_weighted = cached.get("reverse_edges_weighted")
                    if reverse_edges_weighted is None:
                        reverse_edges_weighted = self._build_reverse_edges(edges_weighted)
                    return Graph(
                        nodes=nodes,
                        edges={},
                        edges_weighted=edges_weighted,
                        reverse_edges_weighted=reverse_edges_weighted,
                    )
            except (OSError, pickle.UnpicklingError, ValueError, EOFError):
                pass

        nodes, ways = load_osm_pbf(
            self.pbf_path,
            allowed_highways=set(settings.ROUTE_HIGHWAY_TYPES),
        )
        graph = build_graph_from_ways(
            nodes, [(w.nodes, w.oneway) for w in ways], bidirectional=True
        )

        cache_payload = {
            "pbf_mtime": pbf_mtime,
            "nodes": {
                node_id: (loc.latitude, loc.longitude) for node_id, loc in graph.nodes.items()
            },
            "edges_weighted": graph.edges_weighted,
            "reverse_edges_weighted": graph.reverse_edges_weighted,
        }
        try:
            with cache_path.open("wb") as f:
                pickle.dump(cache_payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        except (OSError, pickle.PicklingError):
            pass

        return graph

    @staticmethod
    def _build_reverse_edges(
        edges_weighted: dict[int, list[tuple[int, float]]],
    ) -> dict[int, list[tuple[int, float]]]:
        """Derive reverse adjacency from forward weighted edges for backward search."""
        reverse_edges: dict[int, list[tuple[int, float]]] = {}
        for node_id, neighbors in edges_weighted.items():
            for neighbor_id, weight in neighbors:
                reverse_edges.setdefault(neighbor_id, []).append((node_id, weight))
        return reverse_edges
