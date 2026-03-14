"""Helpers for simplifying response route geometry.

Used to reduce payload size while preserving the overall route shape and
important snapped transition points.
"""

from __future__ import annotations

import math

from app.schemas.geo_location import GeoLocation

EARTH_RADIUS_M = 6_371_000.0


def simplify_path(
    path: list[GeoLocation],
    *,
    tolerance_m: float,
    preserve_indices: set[int] | None = None,
) -> list[GeoLocation]:
    """
    Simplify response geometry without changing the routed path semantics.

    The first and last points are always preserved. `preserve_indices` can be
    used to keep specific internal points such as snapped transition nodes.
    This helps keep responses compact without losing critical turning points.
    """
    if len(path) <= 2 or tolerance_m <= 0:
        return list(path)

    preserved = {0, len(path) - 1}
    if preserve_indices:
        preserved.update(index for index in preserve_indices if 0 <= index < len(path))

    keep = _simplify_segment(path, 0, len(path) - 1, tolerance_m, preserved)
    keep.update(preserved)

    return [point for index, point in enumerate(path) if index in keep]


def _simplify_segment(
    path: list[GeoLocation],
    start_idx: int,
    end_idx: int,
    tolerance_m: float,
    preserved: set[int],
) -> set[int]:
    """Recursively keep only points that deviate meaningfully from the segment.

    This uses a Ramer-Douglas-Peucker-style split to drop near-collinear points.
    """
    keep = {start_idx, end_idx}
    if end_idx - start_idx <= 1:
        return keep

    internal_preserved = [index for index in preserved if start_idx < index < end_idx]
    if internal_preserved:
        split_points = [start_idx, *sorted(internal_preserved), end_idx]
        for left, right in zip(split_points, split_points[1:]):
            keep.update(_simplify_segment(path, left, right, tolerance_m, preserved))
        return keep

    start = path[start_idx]
    end = path[end_idx]
    split_idx, max_distance = _find_farthest_point(path, start_idx, end_idx, start, end)

    if split_idx is not None and max_distance > tolerance_m:
        keep.update(_simplify_segment(path, start_idx, split_idx, tolerance_m, preserved))
        keep.update(_simplify_segment(path, split_idx, end_idx, tolerance_m, preserved))

    return keep


def _find_farthest_point(
    path: list[GeoLocation],
    start_idx: int,
    end_idx: int,
    start: GeoLocation,
    end: GeoLocation,
) -> tuple[int | None, float]:
    """Return the index and distance of the farthest point from the segment.

    Factored out to keep the recursive logic simple and readable.
    """
    max_distance = -1.0
    split_idx: int | None = None
    for index in range(start_idx + 1, end_idx):
        distance = _point_to_segment_distance_m(path[index], start, end)
        if distance > max_distance:
            max_distance = distance
            split_idx = index
    return split_idx, max_distance


def _point_to_segment_distance_m(point: GeoLocation, start: GeoLocation, end: GeoLocation) -> float:
    """Return the perpendicular distance from a point to a line segment in meters.

    We project locally to approximate meters for small geographic spans.
    """
    px, py = _project_m(point, start)
    sx, sy = 0.0, 0.0
    ex, ey = _project_m(end, start)
    dx = ex - sx
    dy = ey - sy

    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - sx, py - sy)

    projection = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    projection = max(0.0, min(1.0, projection))
    closest_x = sx + projection * dx
    closest_y = sy + projection * dy
    return math.hypot(px - closest_x, py - closest_y)


def _project_m(point: GeoLocation, origin: GeoLocation) -> tuple[float, float]:
    """Project lat/lon to a local planar coordinate system centered on `origin`.

    This keeps distance calculations fast without depending on GIS libraries.
    """
    lat_rad = math.radians(point.latitude)
    origin_lat_rad = math.radians(origin.latitude)
    origin_lon_rad = math.radians(origin.longitude)
    lon_rad = math.radians(point.longitude)

    x = (lon_rad - origin_lon_rad) * math.cos((lat_rad + origin_lat_rad) / 2.0) * EARTH_RADIUS_M
    y = (lat_rad - origin_lat_rad) * EARTH_RADIUS_M
    return x, y
