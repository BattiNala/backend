"""
Haversine distance for geographic routing.

Used as both edge weights and heuristic estimates because it is fast and
accurate enough at city scale without needing projection libraries.
"""

import math

from app.schemas.geo_location import GeoLocation


def haversine(loc1: GeoLocation, loc2: GeoLocation) -> float:
    """
    Calculate the great circle distance in kilometers between two points
    on the Earth specified in decimal degrees using the Haversine formula.

    This is the default distance metric used across routing utilities.
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
    lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Radius of Earth in kilometers (mean radius)
    r = 6371.0
    return c * r
