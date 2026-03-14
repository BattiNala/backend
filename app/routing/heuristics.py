"""Heuristics for pathfinding.

These helpers make it easy to swap in different heuristic functions without
changing the search implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation

NodeId = int


def haversine_heuristic(
    nodes: Mapping[NodeId, GeoLocation],
    goal_id: NodeId,
) -> Callable[[NodeId], float]:
    """Return a heuristic function (in km) using Haversine distance to the goal.

    This is commonly used with A* to prioritize nodes geographically closer
    to the destination.
    """

    def _heuristic(node_id: NodeId) -> float:
        return haversine(nodes[node_id], nodes[goal_id])

    return _heuristic
