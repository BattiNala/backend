"""Dijkstra shortest path implementation for routing over geographic graphs.

This module provides a simple Dijkstra algorithm without heuristics, mirroring the
API of the A* implementation for ease of use in the existing codebase and
tests. It returns the same `AStarResult` dataclass defined in `astar.py` so that
callers can treat both algorithms interchangeably.
"""

# pylint: disable=too-many-locals,too-many-arguments
from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Iterable, Mapping

from app.routing.astar import AStarResult as DijkstraResult
from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation

NodeId = int


def dijkstra_shortest_path(
    nodes: Mapping[NodeId, GeoLocation],
    edges: Mapping[NodeId, Iterable[NodeId] | Iterable[tuple[NodeId, float]]],
    start_id: NodeId,
    goal_id: NodeId,
    *,
    weight_fn: Callable[[GeoLocation, GeoLocation], float] | None = None,
    max_expansions: int | None = None,
) -> DijkstraResult | None:
    """Compute the shortest path between two nodes using Dijkstra's algorithm.

    Parameters
    ----------
    nodes:
        Mapping from node identifier to ``GeoLocation`` coordinates.
    edges:
        Mapping from a node to its adjacency list. Adjacent items may be either a
        plain ``NodeId`` (in which case the edge weight is calculated with
        ``weight_fn``) or a pre-weighted ``(neighbor_id, distance_km)`` tuple.
    start_id, goal_id:
        Identifiers of the source and destination nodes.
    weight_fn:
        Optional callable to compute edge weight from two ``GeoLocation`` objects.
        If omitted, the default ``haversine`` distance is used.
    max_expansions:
        Optional guardrail to stop the search after a certain number of node
        expansions. ``None`` means no limit.

    Returns
    -------
    DijkstraResult | None
        ``DijkstraResult`` containing the path and total distance in kilometres, or
        ``None`` if no path exists or the expansion limit is reached.
    """

    if start_id not in nodes or goal_id not in nodes:
        raise ValueError("start_id and goal_id must exist in nodes")

    if start_id == goal_id:
        return DijkstraResult(path=[start_id], distance_km=0.0)

    weight = weight_fn or haversine

    # Distance from start to each node discovered so far.
    g_score: dict[NodeId, float] = {start_id: 0.0}
    # For path reconstruction.
    came_from: dict[NodeId, NodeId] = {}
    # Priority queue of (distance, node).
    heap: list[tuple[float, NodeId]] = [(0.0, start_id)]
    heapq.heapify(heap)
    expansions = 0

    while heap:
        current_dist, current = heapq.heappop(heap)
        if current == goal_id:
            # Reconstruct path.
            path: list[NodeId] = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return DijkstraResult(path=path, distance_km=current_dist)

        expansions += 1
        if max_expansions is not None and expansions > max_expansions:
            return None

        for edge in edges.get(current, []):
            # Normalise edge representation.
            if isinstance(edge, tuple):
                neighbor, edge_weight = edge
            else:
                neighbor = edge
                if neighbor not in nodes:
                    continue
                edge_weight = weight(nodes[current], nodes[neighbor])

            tentative_g = current_dist + edge_weight
            if tentative_g < g_score.get(neighbor, math.inf):
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                heapq.heappush(heap, (tentative_g, neighbor))

    # Exhausted search without reaching goal.
    return None
