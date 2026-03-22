"""Nearest-node lookup for lat/lon inputs.

Used to snap arbitrary user coordinates onto the routable graph before
running pathfinding, so routes start and end on valid nodes.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.routing.haversine import haversine
from app.routing.spatial_index import GridIndex, nearest_node_id_grid
from app.schemas.geo_location import GeoLocation

NodeId = int


def nearest_node_id(nodes: Mapping[NodeId, GeoLocation], location: GeoLocation) -> NodeId:
    """
    Find the nearest node ID to a given location using Haversine distance.

    This is a simple O(N) scan. For large graphs, consider adding a spatial index.
    It exists as a correctness-first fallback when no index is available.
    """
    nearest_id: NodeId | None = None
    nearest_dist = float("inf")

    for node_id, node_loc in nodes.items():
        dist = haversine(location, node_loc)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_id = node_id

    if nearest_id is None:
        raise ValueError("nodes is empty")

    return nearest_id


def nearest_node_id_indexed(
    index: GridIndex,
    location: GeoLocation,
    *,
    max_radius_cells: int = 50,
) -> NodeId:
    """Find nearest node using a grid index without full-scan fallback.

    This is the preferred path for production traffic to avoid O(N) scans.
    """
    return nearest_node_id_grid(index, location, max_radius_cells=max_radius_cells)
