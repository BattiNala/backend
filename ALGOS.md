# Routing Algorithms

This document explains how the routing API works in this codebase, what algorithms it uses, why `snapped_start` and `snapped_destination` exist, and where the current performance characteristics come from.

## Overview

The routing stack takes two geographic coordinates:

- `start`
- `destination`

It then:

1. loads a routable road graph from OSM data
2. finds the nearest routable graph node for each input coordinate
3. runs shortest-path search between those snapped graph nodes
4. converts the resulting node path into coordinate points
5. optionally inserts the exact request start/end when the request point is not close enough to the snapped road node
6. simplifies the returned geometry so the API does not send every graph node back to the client

The current endpoint is:

- `POST /api/v1/routes/shortest`

Main implementation files:

- [app/api/v1/endpoints/routes.py](app/api/v1/endpoints/routes.py)
- [app/services/route_service.py](app/services/route_service.py)
- [app/routing/astar.py](app/routing/astar.py)
- [app/routing/graph_builder.py](app/routing/graph_builder.py)
- [app/routing/osm_pbf_loader.py](app/routing/osm_pbf_loader.py)
- [app/routing/spatial_index.py](app/routing/spatial_index.py)
- [app/routing/path_simplify.py](app/routing/path_simplify.py)

## Data Source

The road network comes from:

- `kathmandu_valley.osm.pbf`

Configured in:

- [app/core/config.py](app/core/config.py)

Relevant settings:

- `OSM_PBF_PATH`
- `ROUTE_GRAPH_CACHE_PATH`
- `ROUTE_GRID_CELL_SIZE_DEG`
- `ROUTE_MAX_SNAP_DISTANCE_M`
- `ROUTE_RESPONSE_SIMPLIFY_TOLERANCE_M`
- `ROUTE_HIGHWAY_TYPES`

Only selected `highway` types are loaded into the routing graph.

## Graph Construction

Graph loading happens in [app/services/route_service.py](app/services/route_service.py).

### OSM Parsing

[app/routing/osm_pbf_loader.py](app/routing/osm_pbf_loader.py) does the following:

- parses nodes from the `.osm.pbf`
- keeps only ways whose `highway` tag is in `ROUTE_HIGHWAY_TYPES`
- detects one-way roads
- reverses ways whose `oneway=-1` or equivalent means reverse direction
- keeps only nodes that are actually referenced by accepted road ways

### Graph Representation

[app/routing/graph_builder.py](app/routing/graph_builder.py) builds:

- `nodes`: `node_id -> GeoLocation`
- `edges`: unweighted adjacency
- `edges_weighted`: forward adjacency with edge distance in km
- `reverse_edges_weighted`: reverse adjacency with edge distance in km

Edge weights are computed using the Haversine distance between consecutive OSM nodes.

This is a road-network graph cache for the whole map, not a route-result cache for specific user requests.

## Graph Cache

The graph is serialized to:

- `route_graph_cache.pkl`

This cache stores:

- `pbf_mtime`
- graph node coordinates
- forward weighted edges
- reverse weighted edges

The cache is reused only if the OSM file modification time matches.

Important:

- this does not cache routes for specific coordinates
- this does not cache `start -> destination` request results
- this only avoids reparsing and rebuilding the full map graph

## Startup Warm Load

The application now warms the route graph during FastAPI startup in [app/main.py](app/main.py).

Why:

- earlier, the first route request was paying the entire graph build cost
- measured startup graph build was roughly 36 seconds on a cache miss
- actual route search for the sample request was only about 164 ms

So the expensive work is moved to application startup instead of the first real user request.

This means:

- app startup may take longer
- route requests after startup are much faster
- this still does not cache route results for individual coordinates

## Nearest Node Search

Input coordinates are not automatically valid road-graph points.

Examples:

- a user can tap inside a building
- a coordinate can fall in a courtyard
- a destination can be beside a road, not exactly on a road node

So the system first snaps each input coordinate to the nearest routable graph node.

Implementation:

- [app/routing/nearest_node.py](app/routing/nearest_node.py)
- [app/routing/spatial_index.py](app/routing/spatial_index.py)

### Spatial Index

A fixed-size grid index is built over all graph nodes.

For a query location:

1. compute the grid cell
2. search outward by increasing cell radius
3. collect candidate nodes from nearby cells
4. choose the nearest candidate by Haversine distance

This is much faster than scanning all graph nodes for every request.

## What `snapped_start` and `snapped_destination` Mean

These fields are:

- the nearest routable road-network nodes to the request coordinates

They are not:

- necessarily the exact user coordinate
- necessarily the beginning or end of a road
- necessarily the nearest point on a road segment

They represent where the request location attaches to the routing graph.

So:

- `snapped_start` is where the route enters the road graph
- `snapped_destination` is where the route leaves the road graph

If a request coordinate is already very close to a road node, the snapped point will be nearly identical to the request coordinate.

If a request coordinate is off-road, the snapped point may differ more noticeably.

## Shortest Path Search

Implementation:

- [app/routing/astar.py](app/routing/astar.py)

The router uses A* search with Haversine distance as the heuristic.

### How A* Works

A* is a shortest-path search algorithm that tries to reach the goal without exploring the whole graph.

For each node, it tracks:

- `g(n)`: the cost from the start node to node `n`
- `h(n)`: an estimate of the remaining cost from node `n` to the goal
- `f(n) = g(n) + h(n)`: the estimated total cost of a path that goes through node `n`

The algorithm keeps a priority queue of candidate nodes ordered by the lowest `f(n)`.

At a high level:

1. start from the snapped start node
2. put it into the priority queue
3. repeatedly pop the most promising node
4. relax its outgoing edges
5. if a cheaper path to a neighbor is found, update that neighbor's score and parent
6. stop when the goal is reached, then reconstruct the path by walking parents backward

### Why It Is Faster Than Dijkstra

Dijkstra's algorithm uses only the known path cost `g(n)`.

That means it expands outward in all directions based only on already-traveled cost.

A* uses `g(n) + h(n)`, so it prefers nodes that are both:

- cheap to reach so far
- likely to be closer to the goal

If the heuristic is good, A* avoids exploring large irrelevant parts of the graph.

### Heuristic Used Here

This project uses Haversine distance as the heuristic.

That means the estimated remaining cost is the straight-line geographic distance from the current node to the goal.

This is a good fit because:

- road distance is never shorter than straight-line distance
- the heuristic is cheap to compute
- it guides the search toward the destination

In practice, it is an admissible heuristic for this distance-based graph, meaning it should not overestimate the true shortest-path cost.

### Path Reconstruction

While searching, the algorithm stores `came_from[child] = parent`.

When the destination is found:

- start from the goal node
- walk backward through `came_from`
- reverse that sequence

That produces the final ordered route path.

### Current Search Strategy

The current implementation supports:

- single-direction A* if only forward edges are given
- bidirectional A* when reverse edges are available

In this project, routing uses bidirectional A* over:

- `edges_weighted`
- `reverse_edges_weighted`

This reduces the amount of graph explored compared with expanding only from the start side.

### How Bidirectional A* Helps

Instead of searching only:

- from start toward destination

the current implementation also searches:

- backward from destination toward start

The two searches progress until they meet.

This is useful because the search area often grows quickly with distance. Meeting in the middle usually means:

- fewer node expansions
- less heap work
- lower latency on longer routes

The reverse search uses `reverse_edges_weighted`, which is why that reverse adjacency is built and cached.

### Distance Metric

Edge cost and heuristic are both based on Haversine distance in kilometers.

This gives:

- simple implementation
- geographically reasonable heuristic
- no dependency on travel speed or road class cost model

It does not currently model:

- traffic
- turn penalties
- road speed limits
- walking vs driving profiles

## Path Generation

After A* returns the node path, [app/services/route_service.py](app/services/route_service.py) converts node IDs into a list of `GeoLocation` points.

Initially, that path is every graph node in the computed route.

This is accurate, but it can generate a lot of output points for long routes.

## Exact Start and End Handling

The API does not blindly replace the whole route with snapped nodes.

In [app/api/v1/endpoints/routes.py](app/api/v1/endpoints/routes.py):

- if the request `start` is within `ROUTE_MAX_SNAP_DISTANCE_M` of the snapped graph node, the first path point is replaced with the exact request start
- otherwise, the exact request start is inserted before the snapped graph path
- the same rule is applied for the destination

This preserves:

- accurate graph routing
- better UX when the request is already on or very near the road network
- clear off-road to on-road transition when the request point is not close enough to the graph

## Path Simplification

Implementation:

- [app/routing/path_simplify.py](app/routing/path_simplify.py)

The system now simplifies the returned route geometry without changing the actual route search.

### Why This Exists

The raw route path often contains hundreds of points because every graph node is returned.

That increases:

- JSON serialization time
- payload size
- client parsing and rendering cost

### Algorithm

The simplifier is a Douglas-Peucker-style line simplification using projected meter coordinates.

It:

- preserves the first and last points
- accepts a simplification tolerance in meters
- can preserve selected internal indices exactly
- recursively removes intermediate points that stay within the allowed tolerance

### Accuracy Guardrails

To avoid harming endpoint accuracy:

- route search still runs on the full graph
- only the response geometry is simplified
- inserted exact request endpoints are preserved
- if off-road exact start/end points were inserted, the adjacent snapped transition points are also preserved

Current configuration:

- `ROUTE_RESPONSE_SIMPLIFY_TOLERANCE_M = 7.5`

This is intended to reduce redundant points while keeping the visible path shape close to the real route.

## Performance Findings

Measured sample request behavior showed:

- graph build/load on cache miss: about 36.8 seconds
- grid index build: about 210 ms
- snap lookup: negligible compared with graph load
- shortest path search: about 164 ms
- path simplification: about 5.5 ms

Conclusion:

- the main latency issue was not the route search itself
- the main latency issue was loading/building the full graph on first use

That is why startup warming was added.



## Current Limitations

The current implementation is pragmatic and functional, but not yet a full production-grade navigation engine.

Current limitations include:

- snapping is to nearest graph node, not nearest point on a road segment
- edge weights are geometric distances, not travel-time costs
- no turn restrictions beyond one-way handling
- no live traffic or dynamic weighting
- no advanced preprocessing such as contraction hierarchies

## Possible Future Improvements

If routing speed becomes a problem even after startup warm loading, the next improvements should be dataset- and graph-level, not request-level route caching.

Likely options:

- snap to the nearest point on a road segment instead of nearest node
- compress chains of degree-2 nodes into super-edges while preserving geometry
- use landmark-based heuristics
- use contraction hierarchies
- add travel-time-based edge weights instead of pure geometric distance

These would improve routing quality or speed for every new location, without depending on caching individual route requests.

## Tests

Relevant tests:

- [tests/test_astar.py](tests/test_astar.py)
- [tests/test_path_simplify.py](tests/test_path_simplify.py)

These currently verify:

- bidirectional A* correctness on a directed graph
- same-start-and-goal behavior
- simplification removing redundant straight-line points
- simplification preserving required snap-transition points

## A* In Our Case, Explained Very Simply

Imagine Kathmandu's roads are a huge connect-the-dots drawing.

Each dot is:

- a road node from the OSM map

Each line between dots is:

- a road segment you are allowed to travel on

So before A* can do anything, the app first loads this big road drawing into memory.

That means A* is not guessing roads out of nowhere.

It already has:

- the road dots
- which dots connect to which other dots
- how far each connection is

### Step 1: We Find the Closest Road Dots

Suppose the user gives:

- a start location
- a destination location

Those exact points might be:

- inside a building
- beside a road
- in a courtyard
- not exactly on a road node

So the app first finds the nearest usable road dots.

These become:

- `snapped_start`
- `snapped_destination`

You can think of this as:

- "Where do we enter the road network?"
- "Where do we leave the road network?"

### Step 2: A* Starts Walking Through the Road Graph

Now imagine a child trying to go from one dot to another in a maze of roads.

The child does not want to check every road in Kathmandu.

That would be too slow.

So the child uses two ideas at the same time:

- "How far have I already walked?"
- "Which road seems to point closer to the goal?"

That is exactly what A* does.

For every road node it looks at, it keeps two important numbers.

### Number 1: `g`

`g` means:

- the real distance already traveled from the snapped start to this node

So if A* has walked through several road segments to reach a node, `g` is the sum of those segment distances.

This part is not a guess.

It is the real known cost so far.

### Number 2: `h`

`h` means:

- a guess of how far this node still is from the destination

In this project, that guess is:

- straight-line Haversine distance from the current node to the goal node

This is like a child pointing at the destination and saying:

- "It looks roughly this far away as the crow flies."

That does not mean the child can fly through buildings.

It is only a hint for direction.

### Number 3: `f = g + h`

Then A* adds them:

- `f = g + h`

This means:

- "How expensive is this path so far, plus how promising does it look from here?"

So A* prefers nodes that are:

- cheap to reach already
- and seem closer to the destination

### Step 3: A* Keeps a "Most Promising Next Road" List

A* stores candidate nodes in a priority queue.

You can imagine this as a smart to-do list:

- the most promising road node is always at the top

Each time, A* picks the best-looking next node and explores from there.

When it explores a node, it checks:

- which neighboring road nodes can be reached from here
- how much extra distance each move adds

If A* finds a cheaper way to reach a neighbor than it knew before, it updates that neighbor's information.

It also remembers:

- "I reached this node from that previous node"

That remembered parent link is later used to rebuild the final route.

### Step 4: Why It Does Not Need To Check Every Road

If we used a dumb search, we might expand roads in many wrong directions.

But A* uses the heuristic `h`, so it tends to move toward the destination instead of spreading everywhere.

That is why it is faster than checking all possibilities.

In simple words:

- the map gives A* the real roads
- the heuristic gives A* a sense of direction

It needs both.

If it had:

- only the heuristic and no map

then it would not know what roads exist.

If it had:

- only the map and no heuristic

then it could still work, but it would explore much more and usually be slower.

### Step 5: In Our Project, Search Happens From Both Sides

Our implementation uses bidirectional A*.

That means:

- one search starts from `snapped_start`
- another search starts from `snapped_destination`

They move through the road graph toward each other.

This is like two children starting from opposite ends of the city and trying to meet in the middle instead of only one child doing all the searching.

Why this helps:

- each side usually explores less area
- the searches often meet faster than a one-sided search would reach the goal

For this to work, we store:

- forward road edges
- reverse road edges

So one side can search forward and the other side can search backward correctly.

### Step 6: How The Final Route Is Built

While searching, A* stores parent links.

That means it remembers things like:

- "to get to node C, I came from node B"
- "to get to node B, I came from node A"

When the search reaches the goal, or when the two bidirectional searches meet, the app can reconstruct the route by following those remembered links backward.

Then it reverses that chain into the correct order.

So the final route is not guessed afterward.

It is rebuilt from the exact road nodes A* actually chose.

### Step 7: What Happens After A* Finds The Route

Once A* returns the node path:

1. node IDs are converted into latitude/longitude points
2. the exact request start/end may be inserted or substituted depending on snap distance
3. the returned geometry is simplified so the response is not packed with every tiny intermediate road node

Important:

- simplification happens after routing
- it does not change how A* chooses the path
- it only reduces extra response points

### A One-Sentence Summary

In this project, A* is like a child walking through a preloaded road-dot map of Kathmandu, always choosing the next road that is both cheap so far and seems closer to the destination, until the two sides of the search meet and the final road path can be rebuilt.
