"""A* shortest path implementation for routing over geographic graphs.

Provides a configurable single- or bi-directional search so higher-level
services can compute routes efficiently without coupling to graph storage.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from app.routing.haversine import haversine
from app.schemas.geo_location import GeoLocation

NodeId = int


@dataclass(frozen=True, slots=True)
class AStarResult:
    """Output of a route search, used by API responses and tests."""

    path: list[NodeId]
    distance_km: float


@dataclass(frozen=True, slots=True)
class AStarConfig:
    """Configuration for A* weighting and guardrails.

    This keeps advanced tuning optional while avoiding bloated function
    signatures in the route service.
    """

    weight_fn: Callable[[GeoLocation, GeoLocation], float] | None = None
    heuristic_fn: Callable[[GeoLocation, GeoLocation], float] | None = None
    max_expansions: int | None = None
    reverse_edges: Mapping[NodeId, Iterable[tuple[NodeId, float]]] | None = None


@dataclass(slots=True)
class _SearchSide:
    """State for one direction of search."""

    heap: list[tuple[float, int, NodeId]]
    came_from: dict[NodeId, NodeId]
    g_score: dict[NodeId, float]
    closed: set[NodeId]


@dataclass(slots=True)
class _BidirectionalState:
    """Mutable state for bidirectional expansion to keep the main loop small."""

    forward: _SearchSide
    backward: _SearchSide
    counter: int
    best_distance: float
    meeting_node: NodeId | None
    expansions: int


@dataclass(frozen=True, slots=True)
class _FrontierView:
    """Read-only view of the currently expanding frontier."""

    heap: list[tuple[float, int, NodeId]]
    closed: set[NodeId]
    own_g: dict[NodeId, float]
    other_g: dict[NodeId, float]
    came_from: dict[NodeId, NodeId]
    adjacency: Mapping[NodeId, Iterable[tuple[NodeId, float]]]
    target_id: NodeId


@dataclass(slots=True)
class _SingleDirectionState:
    """State for single-direction A* to reduce local variables."""

    open_heap: list[tuple[float, int, NodeId]]
    came_from: dict[NodeId, NodeId]
    g_score: dict[NodeId, float]
    closed: set[NodeId]
    counter: int
    expansions: int


def _reconstruct_path(came_from: dict[NodeId, NodeId], current: NodeId) -> list[NodeId]:
    """Rebuild a forward path by following parent pointers back to the start.

    We keep this separate to make both single and bidirectional search share
    the same path materialization logic.
    """
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _reconstruct_bidirectional_path(
    forward_came_from: dict[NodeId, NodeId],
    backward_came_from: dict[NodeId, NodeId],
    meeting_node: NodeId,
) -> list[NodeId]:
    """Join the forward and backward search trees at the meeting node.

    This preserves the forward ordering expected by callers even though the
    search advanced from both ends.
    """
    path = _reconstruct_path(forward_came_from, meeting_node)

    current = meeting_node
    while current in backward_came_from:
        current = backward_came_from[current]
        path.append(current)

    return path


def _astar_single_direction(
    nodes: Mapping[NodeId, GeoLocation],
    edges: Mapping[NodeId, Iterable[NodeId] | Iterable[tuple[NodeId, float]]],
    start_id: NodeId,
    goal_id: NodeId,
    *,
    config: AStarConfig,
) -> AStarResult | None:
    """Run classic one-direction A* from start to goal.

    Used when reverse edges are unavailable to keep memory and setup minimal.
    """
    weight = config.weight_fn or haversine
    heuristic = config.heuristic_fn or haversine

    state = _init_single_state(nodes, start_id, goal_id, heuristic)

    while state.open_heap:
        _, _, current = heapq.heappop(state.open_heap)

        if current in state.closed:
            continue
        if current == goal_id:
            return AStarResult(
                path=_reconstruct_path(state.came_from, current),
                distance_km=state.g_score[current],
            )

        state.closed.add(current)
        state.expansions += 1
        if config.max_expansions is not None and state.expansions > config.max_expansions:
            return None

        for edge in edges.get(current, []):
            neighbor, edge_weight = _unpack_edge(edge, nodes, current, weight)
            if neighbor is None or neighbor in state.closed:
                continue

            tentative_g = state.g_score[current] + edge_weight
            if tentative_g < state.g_score.get(neighbor, math.inf):
                state.came_from[neighbor] = current
                state.g_score[neighbor] = tentative_g
                state.counter += 1
                f_score = tentative_g + heuristic(nodes[neighbor], nodes[goal_id])
                heapq.heappush(state.open_heap, (f_score, state.counter, neighbor))

    return None


def _init_single_state(
    nodes: Mapping[NodeId, GeoLocation],
    start_id: NodeId,
    goal_id: NodeId,
    heuristic: Callable[[GeoLocation, GeoLocation], float],
) -> _SingleDirectionState:
    """Initialize heap and maps for single-direction A*."""
    open_heap: list[tuple[float, int, NodeId]] = []
    counter = 0
    start_h = heuristic(nodes[start_id], nodes[goal_id])
    heapq.heappush(open_heap, (start_h, counter, start_id))
    return _SingleDirectionState(
        open_heap=open_heap,
        came_from={},
        g_score={start_id: 0.0},
        closed=set(),
        counter=counter,
        expansions=0,
    )


def _unpack_edge(
    edge: NodeId | tuple[NodeId, float],
    nodes: Mapping[NodeId, GeoLocation],
    current: NodeId,
    weight: Callable[[GeoLocation, GeoLocation], float],
) -> tuple[NodeId | None, float]:
    """Normalize an edge to (neighbor, weight) regardless of representation."""
    if isinstance(edge, tuple):
        return edge
    if edge not in nodes:
        return None, 0.0
    return edge, weight(nodes[current], nodes[edge])


def _init_bidirectional_state(
    nodes: Mapping[NodeId, GeoLocation],
    start_id: NodeId,
    goal_id: NodeId,
    heuristic: Callable[[GeoLocation, GeoLocation], float],
) -> _BidirectionalState:
    """Initialize heaps and maps for a two-frontier search.

    Centralizing setup keeps the main loop focused on expansion and pruning.
    """
    forward_heap: list[tuple[float, int, NodeId]] = []
    backward_heap: list[tuple[float, int, NodeId]] = []
    counter = 0
    heapq.heappush(forward_heap, (heuristic(nodes[start_id], nodes[goal_id]), counter, start_id))
    counter += 1
    heapq.heappush(backward_heap, (heuristic(nodes[goal_id], nodes[start_id]), counter, goal_id))
    forward = _SearchSide(
        heap=forward_heap,
        came_from={},
        g_score={start_id: 0.0},
        closed=set(),
    )
    backward = _SearchSide(
        heap=backward_heap,
        came_from={},
        g_score={goal_id: 0.0},
        closed=set(),
    )
    return _BidirectionalState(
        forward=forward,
        backward=backward,
        counter=counter,
        best_distance=math.inf,
        meeting_node=None,
        expansions=0,
    )


def _select_frontier(
    state: _BidirectionalState,
    edges: Mapping[NodeId, Iterable[tuple[NodeId, float]]],
    reverse_edges: Mapping[NodeId, Iterable[tuple[NodeId, float]]],
    start_id: NodeId,
    goal_id: NodeId,
) -> _FrontierView:
    """Choose which frontier to expand to balance search progress."""
    expand_forward = state.forward.heap[0][0] <= state.backward.heap[0][0]
    if expand_forward:
        return _FrontierView(
            heap=state.forward.heap,
            closed=state.forward.closed,
            own_g=state.forward.g_score,
            other_g=state.backward.g_score,
            came_from=state.forward.came_from,
            adjacency=edges,
            target_id=goal_id,
        )
    return _FrontierView(
        heap=state.backward.heap,
        closed=state.backward.closed,
        own_g=state.backward.g_score,
        other_g=state.forward.g_score,
        came_from=state.backward.came_from,
        adjacency=reverse_edges,
        target_id=start_id,
    )


def _expand_frontier(
    nodes: Mapping[NodeId, GeoLocation],
    state: _BidirectionalState,
    frontier: _FrontierView,
    heuristic: Callable[[GeoLocation, GeoLocation], float],
    max_expansions: int | None,
) -> bool:
    """Expand one frontier and update the current best meeting point.

    Returns True when the search should abort due to expansion limits.
    """
    _, _, current = heapq.heappop(frontier.heap)
    if current in frontier.closed:
        return False

    frontier.closed.add(current)
    state.expansions += 1
    if max_expansions is not None and state.expansions > max_expansions:
        return True

    if current in frontier.other_g:
        total_distance = frontier.own_g[current] + frontier.other_g[current]
        if total_distance < state.best_distance:
            state.best_distance = total_distance
            state.meeting_node = current

    for neighbor, edge_weight in frontier.adjacency.get(current, []):
        if neighbor not in nodes or neighbor in frontier.closed:
            continue

        tentative_g = frontier.own_g[current] + edge_weight
        if tentative_g >= frontier.own_g.get(neighbor, math.inf):
            continue

        frontier.came_from[neighbor] = current
        frontier.own_g[neighbor] = tentative_g

        if neighbor in frontier.other_g:
            total_distance = tentative_g + frontier.other_g[neighbor]
            if total_distance < state.best_distance:
                state.best_distance = total_distance
                state.meeting_node = neighbor

        state.counter += 1
        f_score = tentative_g + heuristic(nodes[neighbor], nodes[frontier.target_id])
        heapq.heappush(frontier.heap, (f_score, state.counter, neighbor))

    return False


def _astar_bidirectional(
    nodes: Mapping[NodeId, GeoLocation],
    edges: Mapping[NodeId, Iterable[tuple[NodeId, float]]],
    start_id: NodeId,
    goal_id: NodeId,
    config: AStarConfig,
) -> AStarResult | None:
    """Run bidirectional A* to reduce search time on large graphs."""
    heuristic = config.heuristic_fn or haversine
    reverse_edges = config.reverse_edges
    if reverse_edges is None:
        return None
    state = _init_bidirectional_state(nodes, start_id, goal_id, heuristic)

    while state.forward.heap and state.backward.heap:
        if state.forward.heap[0][0] + state.backward.heap[0][0] >= state.best_distance:
            break

        frontier = _select_frontier(state, edges, reverse_edges, start_id, goal_id)
        aborted = _expand_frontier(nodes, state, frontier, heuristic, config.max_expansions)
        if aborted:
            return None

    if state.meeting_node is None:
        return None

    return AStarResult(
        path=_reconstruct_bidirectional_path(
            state.forward.came_from, state.backward.came_from, state.meeting_node
        ),
        distance_km=state.best_distance,
    )


def astar_shortest_path(
    nodes: Mapping[NodeId, GeoLocation],
    edges: Mapping[NodeId, Iterable[NodeId] | Iterable[tuple[NodeId, float]]],
    start_id: NodeId,
    goal_id: NodeId,
    *,
    config: AStarConfig | None = None,
) -> AStarResult | None:
    """
    Compute the shortest path between two graph nodes using A*.

    `nodes` contains the geographic coordinates for each graph node.
    `edges` contains forward adjacency; each edge may be pre-weighted as
    `(neighbor_id, distance_km)` or provided as a bare neighbor node id.

    If `config.reverse_edges` is provided, the search runs bidirectionally:
    one frontier expands from the start while another expands from the goal.
    Otherwise the function falls back to the simpler one-direction variant.

    `config` controls weight/heuristic functions and the expansion guardrail,
    letting callers tune performance without reworking the search logic.
    """
    if start_id not in nodes or goal_id not in nodes:
        raise ValueError("start_id and goal_id must exist in nodes")

    if start_id == goal_id:
        return AStarResult(path=[start_id], distance_km=0.0)

    config = config or AStarConfig()

    if config.reverse_edges is None:
        return _astar_single_direction(
            nodes,
            edges,
            start_id,
            goal_id,
            config=config,
        )

    return _astar_bidirectional(
        nodes,
        edges,
        start_id,
        goal_id,
        config,
    )
