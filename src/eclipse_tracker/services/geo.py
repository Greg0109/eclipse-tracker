"""Pure geographic math helpers: distance, bearing, and polyline interpolation.

No I/O, no external calls - kept pure so it is trivially unit-testable.
"""

import math


EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers between two lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial compass bearing (0-360, 0=N) from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360) % 360


def destination_point(lat: float, lon: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    """Point reached from (lat, lon) travelling `distance_km` along `bearing_deg`."""
    delta = distance_km / EARTH_RADIUS_KM
    theta = math.radians(bearing_deg)
    phi1 = math.radians(lat)
    lambda1 = math.radians(lon)

    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540) % 360 - 180


def is_within_range(lat1: float, lon1: float, lat2: float, lon2: float, range_km: float) -> bool:
    """Whether point 2 lies within `range_km` of point 1."""
    return haversine_km(lat1, lon1, lat2, lon2) <= range_km


def bounding_box(lat: float, lon: float, range_km: float) -> tuple[float, float, float, float]:
    """Conservative (min_lat, min_lon, max_lat, max_lon) box containing the range_km circle."""
    lat_delta = range_km / EARTH_RADIUS_KM * (180 / math.pi)
    lon_delta = lat_delta / max(math.cos(math.radians(lat)), 0.01)
    return (lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta)


def nearest_point_on_polyline(
    lat: float,
    lon: float,
    polyline: list[tuple[float, float]],
) -> tuple[int, float]:
    """
    Index of the polyline vertex closest to (lat, lon), and the fractional position [0, 1]
    of the projection onto the nearest segment (0 = at that vertex, 1 = at the next vertex).

    Uses an equirectangular flat-earth approximation for the projection, which is accurate
    enough for the short segment lengths in a bundled eclipse centerline (tens of km apart).
    """
    best_idx = 0
    best_dist = math.inf
    best_frac = 0.0

    for i in range(len(polyline) - 1):
        ax, ay = polyline[i][1], polyline[i][0]
        bx, by = polyline[i + 1][1], polyline[i + 1][0]
        px, py = lon, lat

        cos_lat = math.cos(math.radians(lat))
        abx, aby = (bx - ax) * cos_lat, by - ay
        apx, apy = (px - ax) * cos_lat, py - ay

        seg_len_sq = abx * abx + aby * aby
        frac = 0.0 if seg_len_sq == 0 else max(0.0, min(1.0, (apx * abx + apy * aby) / seg_len_sq))

        proj_lat = polyline[i][0] + frac * (polyline[i + 1][0] - polyline[i][0])
        proj_lon = polyline[i][1] + frac * (polyline[i + 1][1] - polyline[i][1])
        dist = haversine_km(lat, lon, proj_lat, proj_lon)

        if dist < best_dist:
            best_dist = dist
            best_idx = i
            best_frac = frac

    return best_idx, best_frac
