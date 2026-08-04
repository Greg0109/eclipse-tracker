"""
Horizon-obstruction estimate using the public Open-Elevation API.

Approach: sample ground elevation along a ray from the candidate point toward the sun's
azimuth (the direction totality will be visible in), out to a few km, and compute the
angle to the highest point on that ray as seen from the candidate. If that horizon angle
is close to or above the sun's altitude during totality, the view is likely obstructed by
terrain in that direction. This is a 2D-profile proxy, not a full 3D viewshed, and it does
not model vegetation - it is a reasonable signal for "blocked by a mountain ridge", not a
precise line-of-sight guarantee.
"""

from __future__ import annotations

import math

import httpx

from eclipse_tracker.services.cache import TTLCache
from eclipse_tracker.services.geo import destination_point
from eclipse_tracker.services.http_retry import with_retries


class TerrainService:
    """Fetches and caches horizon-clearance estimates from Open-Elevation."""

    def __init__(
        self,
        elevation_url: str,
        user_agent: str,
        timeout_s: float,
        cache_ttl_s: float,
        *,
        ray_samples: int = 8,
        ray_max_km: float = 5.0,
    ) -> None:
        """Configure the Open-Elevation endpoint, request timeout, cache TTL, and ray-cast resolution."""
        self._elevation_url = elevation_url
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._ray_samples = ray_samples
        self._ray_max_km = ray_max_km
        self._cache: TTLCache[float] = TTLCache(cache_ttl_s)

    async def horizon_clearance_deg(
        self, lat: float, lon: float, sun_azimuth_deg: float, sun_altitude_deg: float
    ) -> float:
        """
        Degrees of clearance between the sun's altitude and the terrain horizon along its
        azimuth. Positive means the sun sits above the local horizon by that many degrees
        (better); zero or negative means terrain likely blocks the view.
        """
        key = f"{lat:.3f},{lon:.3f},{sun_azimuth_deg:.1f}"
        horizon_angle = await self._cache.get_or_set(key, lambda: self._horizon_angle(lat, lon, sun_azimuth_deg))
        return sun_altitude_deg - horizon_angle

    async def _horizon_angle(self, lat: float, lon: float, azimuth_deg: float) -> float:
        step_km = self._ray_max_km / self._ray_samples
        points = [(lat, lon)] + [
            destination_point(lat, lon, azimuth_deg, step_km * i) for i in range(1, self._ray_samples + 1)
        ]

        async def fetch() -> list[dict]:
            async with httpx.AsyncClient(timeout=self._timeout_s, headers={"User-Agent": self._user_agent}) as client:
                locations = "|".join(f"{p_lat},{p_lon}" for p_lat, p_lon in points)
                response = await client.get(self._elevation_url, params={"locations": locations})
                response.raise_for_status()
                return response.json()["results"]

        results = await with_retries(fetch)

        origin_elevation = results[0]["elevation"]
        best_angle = -90.0
        for i, result in enumerate(results[1:], start=1):
            distance_km = step_km * i
            rise_m = result["elevation"] - origin_elevation
            angle = math.degrees(math.atan2(rise_m, distance_km * 1000))
            best_angle = max(best_angle, angle)
        return best_angle
