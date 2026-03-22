"""Route planning endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.route import RouteRequest, RouteResponse
from app.services.route_service import RouteService

router = APIRouter()

_route_service = RouteService(
    pbf_path=Path(settings.OSM_PBF_PATH),
    grid_cell_size_deg=settings.ROUTE_GRID_CELL_SIZE_DEG,
)


@router.post(
    "/shortest",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate shortest route between two coordinates",
)
def shortest_route(payload: RouteRequest) -> RouteResponse:
    """Route between two coordinates and return snapped endpoints plus path geometry."""
    try:
        snapped_start = _route_service.nearest_node(payload.start)
        snapped_destination = _route_service.nearest_node(payload.destination)
        result = _route_service.shortest_path_between_nodes(
            snapped_start.node_id,
            snapped_destination.node_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No route found",
                "snapped_start": snapped_start.location.model_dump(),
                "snapped_destination": snapped_destination.location.model_dump(),
                "snapped_start_distance_m": snapped_start.distance_m,
                "snapped_destination_distance_m": snapped_destination.distance_m,
            },
        )

    path_locations = _route_service.path_to_locations(result)
    if not path_locations:
        raise HTTPException(status_code=404, detail="No route found")

    # Build a single path from the exact start to the exact destination.
    # If the snap distance is too large, insert a straight-line segment.
    if snapped_start.distance_m > settings.ROUTE_MAX_SNAP_DISTANCE_M:
        path_locations.insert(0, payload.start)
    else:
        path_locations[0] = payload.start

    if snapped_destination.distance_m > settings.ROUTE_MAX_SNAP_DISTANCE_M:
        path_locations.append(payload.destination)
    else:
        path_locations[-1] = payload.destination

    preserve_indices = {0, len(path_locations) - 1}
    if snapped_start.distance_m > settings.ROUTE_MAX_SNAP_DISTANCE_M and len(path_locations) > 1:
        preserve_indices.add(1)
    if (
        snapped_destination.distance_m > settings.ROUTE_MAX_SNAP_DISTANCE_M
        and len(path_locations) > 1
    ):
        preserve_indices.add(len(path_locations) - 2)

    path_locations = _route_service.simplify_path(
        path_locations,
        tolerance_m=settings.ROUTE_RESPONSE_SIMPLIFY_TOLERANCE_M,
        preserve_indices=preserve_indices,
    )

    return RouteResponse(
        distance_km=result.distance_km,
        path=path_locations,
        snapped_start=snapped_start.location,
        snapped_destination=snapped_destination.location,
    )
