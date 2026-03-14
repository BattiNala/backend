"""Simple grid-based spatial index for nearest-node lookups.

Used to accelerate snapping by limiting distance checks to nearby cells.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation

NodeId = int


@dataclass(frozen=True, slots=True)
class GridIndex:
    """Grid index that buckets nodes into fixed-size degree cells.

    This trades a small amount of memory for much faster nearest-node queries.
    """

    cell_size_deg: float
    cells: dict[tuple[int, int], list[NodeId]]
    nodes: Mapping[NodeId, GeoLocation]

    def cell_key(self, location: GeoLocation) -> tuple[int, int]:
        """Map a coordinate to its fixed-size grid cell.

        We use integer division by cell size to produce stable buckets.
        """
        return (
            int(location.latitude // self.cell_size_deg),
            int(location.longitude // self.cell_size_deg),
        )


def build_grid_index(
    nodes: Mapping[NodeId, GeoLocation],
    *,
    cell_size_deg: float = 0.005,
) -> GridIndex:
    """Bucket graph nodes into degree-based cells for fast local lookup.

    Call this once after loading the graph so snapping requests stay cheap.
    """
    cells: dict[tuple[int, int], list[NodeId]] = {}

    for node_id, loc in nodes.items():
        key = (
            int(loc.latitude // cell_size_deg),
            int(loc.longitude // cell_size_deg),
        )
        cells.setdefault(key, []).append(node_id)

    return GridIndex(cell_size_deg=cell_size_deg, cells=cells, nodes=nodes)


def nearest_node_id_grid(
    index: GridIndex,
    location: GeoLocation,
    *,
    max_radius_cells: int = 50,
) -> NodeId:
    """
    Find nearest node using grid index without full-scan fallback.

    If no nodes are found within max_radius_cells, raises a ValueError.
    This protects against silently returning a bad snap in empty regions.
    """
    center = index.cell_key(location)
    candidates: list[NodeId] = []

    for radius in range(0, max_radius_cells + 1):
        for key in _iter_cell_keys(center, radius):
            candidates.extend(index.cells.get(key, []))
        if candidates:
            break

    if not candidates:
        raise ValueError("No nodes found within max_radius_cells")

    nearest_id: NodeId | None = None
    nearest_dist = float("inf")

    for node_id in candidates:
        dist = haversine(location, index.nodes[node_id])
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_id = node_id

    if nearest_id is None:
        raise ValueError("No nodes found in candidate cells")

    return nearest_id


def _iter_cell_keys(center: tuple[int, int], radius: int):
    """Yield the square ring of cells at the given radius around `center`.

    This expands search in predictable layers until candidates are found.
    """
    if radius == 0:
        yield center
        return

    cx, cy = center
    for dx in range(-radius, radius + 1):
        yield (cx + dx, cy - radius)
        yield (cx + dx, cy + radius)
    for dy in range(-radius + 1, radius):
        yield (cx - radius, cy + dy)
        yield (cx + radius, cy + dy)
