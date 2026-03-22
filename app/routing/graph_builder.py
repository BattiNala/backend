"""
Graph helpers for routing over OSM-derived data.

This module converts parsed nodes and ways into adjacency lists and weighted
edges so search algorithms can run without caring about OSM parsing details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation

NodeId = int


@dataclass(frozen=True, slots=True)
class Graph:
    """In-memory graph representation for routing.

    We store both weighted and unweighted adjacencies so callers can choose
    fast lookups or accurate distances without rebuilding the graph.
    """

    nodes: dict[NodeId, GeoLocation]
    edges: dict[NodeId, list[NodeId]]
    edges_weighted: dict[NodeId, list[tuple[NodeId, float]]]
    reverse_edges_weighted: dict[NodeId, list[tuple[NodeId, float]]]


def _iter_way_nodes(way: Iterable[NodeId] | tuple[Iterable[NodeId], bool]):
    """Normalize way inputs to (node list, oneway flag) for graph building."""
    if isinstance(way, tuple) and len(way) == 2:
        nodes, oneway = way
        return list(nodes), bool(oneway)
    return list(way), False


def build_graph_from_ways(
    nodes: dict[NodeId, GeoLocation],
    ways: Iterable[Iterable[NodeId] | tuple[Iterable[NodeId], bool]],
    *,
    bidirectional: bool = True,
) -> Graph:
    """
    Build a graph from OSM ways.

    Each way is an ordered sequence of node IDs. We connect consecutive node IDs
    as edges. If bidirectional=True, edges are added in both directions unless
    the way is marked as one-way.

    This is used by the route service to transform parsed OSM data into a
    structure that A* can traverse efficiently.
    """
    edges: dict[NodeId, list[NodeId]] = {}
    edges_weighted: dict[NodeId, list[tuple[NodeId, float]]] = {}
    reverse_edges_weighted: dict[NodeId, list[tuple[NodeId, float]]] = {}

    for way in ways:
        node_ids, oneway = _iter_way_nodes(way)
        if len(node_ids) < 2:
            continue
        prev: NodeId | None = None
        for node_id in node_ids:
            if node_id not in nodes:
                prev = None
                continue
            if prev is not None and prev in nodes:
                edges.setdefault(prev, []).append(node_id)
                if bidirectional and not oneway:
                    edges.setdefault(node_id, []).append(prev)
                dist = haversine(nodes[prev], nodes[node_id])
                edges_weighted.setdefault(prev, []).append((node_id, dist))
                reverse_edges_weighted.setdefault(node_id, []).append((prev, dist))
                if bidirectional and not oneway:
                    edges_weighted.setdefault(node_id, []).append((prev, dist))
                    reverse_edges_weighted.setdefault(prev, []).append((node_id, dist))
            prev = node_id

    return Graph(
        nodes=nodes,
        edges=edges,
        edges_weighted=edges_weighted,
        reverse_edges_weighted=reverse_edges_weighted,
    )
