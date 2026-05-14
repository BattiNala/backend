import time
from pathlib import Path

from app.core.config import settings
from app.schemas.geo_location import GeoLocation
from app.services.route_service import RouteService


def test_astar_with_multiple_routes():
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

    # Independent routes to test
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

    for route in routes:
        name = route["name"]
        start_loc = route["start"]
        end_loc = route["end"]

        search_start_time = time.time()
        result = service.shortest_path(start_loc, end_loc)
        search_duration = (time.time() - search_start_time) * 1000

        if result:
            print(
                f"{name:<45} |  {result.distance_km:>9.1f} | "
                f"{len(result.path):>5} | {search_duration:>9.2f}"
            )
        else:
            print(f"{name:<45} | {'FAILED':>9} | {'-':>5} | {search_duration:>9.2f}")

    print("-" * 80)


if __name__ == "__main__":
    test_astar_with_multiple_routes()
