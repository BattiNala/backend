import time
from pathlib import Path

from app.core.config import settings
from app.routing.dijkstra import DijkstraResult, dijkstra_shortest_path
from app.schemas.geo_location import GeoLocation
from app.services.route_service import RouteService


def test_dijkstra_with_multiple_routes():
    pbf_path = Path(settings.OSM_PBF_PATH)
    if not pbf_path.exists():
        print(f"Error: OSM PBF file not found at {pbf_path}")
        return

    print(f"Initializing RouteService with {pbf_path}...")
    service = RouteService(pbf_path=pbf_path)

    start_time = time.time()
    service.ensure_loaded()
    load_time = time.time() - start_time
    print(f"Graph loaded in {load_time:.2f} seconds.\n")

    routes = [
        {
            "name": "Patan to Kathmandu (Basantapur)",
            "start": GeoLocation(latitude=27.6727, longitude=85.3253),  # Patan Durbar Square
            "end": GeoLocation(latitude=27.7042, longitude=85.3072),  # Basantapur
        },
        {
            "name": "Pashupatinath to Kalanki",
            "start": GeoLocation(latitude=27.7104, longitude=85.3484),  # Pashupatinath
            "end": GeoLocation(latitude=27.6938, longitude=85.2817),  # Kalanki Chowk
        },
        {
            "name": "Swayambhunath to Boudhanath",
            "start": GeoLocation(latitude=27.7149, longitude=85.2903),  # Swayambhu
            "end": GeoLocation(latitude=27.7215, longitude=85.3620),  # Boudha
        },
        {
            "name": "Thamel to Tribhuvan International Airport",
            "start": GeoLocation(latitude=27.7151, longitude=85.3123),  # Thamel
            "end": GeoLocation(latitude=27.6974, longitude=85.3585),  # TIA
        },
    ]

    print(f"{'Route Name':<45} | {'Dist (km)':<10} | {'Nodes':<5} | {'Time (ms)':<10}")
    print("-" * 80)

    nodes = service._graph.nodes
    edges = service._graph.edges_weighted or service._graph.edges

    for route in routes:
        name = route["name"]
        start_node = service.nearest_node(route["start"]).node_id
        end_node = service.nearest_node(route["end"]).node_id

        dijkstra_start = time.time()
        dijkstra_res: DijkstraResult | None = dijkstra_shortest_path(
            nodes, edges, start_node, end_node
        )
        dijkstra_time = (time.time() - dijkstra_start) * 1000

        if dijkstra_res:
            print(
                f"{name:<45} | {dijkstra_res.distance_km:>9.1f} | "
                f"{len(dijkstra_res.path):>5} | {dijkstra_time:>9.2f}"
            )
        else:
            print(f"{name:<45} | {'FAILED':>9} | {'-':>5} | {dijkstra_time:>9.2f}")

    print("-" * 80)


if __name__ == "__main__":
    test_dijkstra_with_multiple_routes()
