"""Load OSM PBF data into simple node/way structures.

We keep this loader focused on extracting routing-relevant primitives so the
graph builder can stay format-agnostic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import osmium

from app.schemas.geo_location import GeoLocation

NodeId = int


@dataclass(frozen=True, slots=True)
class Way:
    """A lightweight way representation for routing.

    Captures only what the graph builder needs: ordered node IDs and oneway
    metadata.
    """

    nodes: list[NodeId]
    oneway: bool


def _is_oneway(tags: dict[str, str]) -> tuple[bool, bool]:
    """
    Determine oneway status.

    Returns (is_oneway, reverse). If reverse=True, the way should be reversed.
    This keeps OSM-specific tag handling out of the graph builder.
    """
    oneway = tags.get("oneway")
    if oneway is None:
        if tags.get("junction") == "roundabout":
            return True, False
        return False, False

    normalized = oneway.lower()
    if normalized in {"yes", "true", "1"}:
        return True, False
    if normalized in {"-1", "reverse"}:
        return True, True

    return False, False


def load_osm_pbf(
    path: str | Path,
    *,
    allowed_highways: set[str] | None = None,
) -> tuple[dict[NodeId, GeoLocation], list[Way]]:
    """
    Load nodes and ways from an OSM .pbf file.

    Requires the 'pyosmium' package.
    Use this to build a routing graph from raw OSM extracts.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    nodes: dict[NodeId, GeoLocation] = {}
    ways: list[Way] = []
    highway_node_ids: set[NodeId] = set()

    if allowed_highways is None:
        allowed_highways = {
            "motorway",
            "trunk",
            "primary",
            "secondary",
            "tertiary",
            "residential",
            "service",
            "unclassified",
            "living_street",
            "road",
        }

    class _Handler(osmium.SimpleHandler):
        def node(self, n):  # type: ignore[override]
            """Collect valid node coordinates."""
            if n.location and n.location.valid():
                nodes[n.id] = GeoLocation(latitude=n.location.lat, longitude=n.location.lon)

        def way(self, w):  # type: ignore[override]
            """Collect routable highway ways."""
            highway = w.tags.get("highway")
            if not highway or highway not in allowed_highways:
                return

            node_ids = [nd.ref for nd in w.nodes]
            if len(node_ids) < 2:
                return

            highway_node_ids.update(node_ids)

            oneway, reverse = _is_oneway(dict(w.tags))
            if reverse:
                node_ids.reverse()

            ways.append(Way(nodes=node_ids, oneway=oneway))

    handler = _Handler()
    handler.apply_file(str(path), locations=True)

    if highway_node_ids:
        nodes = {node_id: loc for node_id, loc in nodes.items() if node_id in highway_node_ids}

    return nodes, ways
