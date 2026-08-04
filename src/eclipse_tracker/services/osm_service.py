"""
OpenStreetMap data access via the public Overpass API.

Used for three things:
  1. Finding real, named, publicly-reachable candidate viewing spots (viewpoints, peaks,
     beaches, parks, attractions) instead of scoring arbitrary lat/lon grid points.
  2. A cheap urban-obstruction / accessibility proxy: building density and nearby roads.
  3. Points of interest (restaurants, cafes, sightseeing) to build a day itinerary.

Please be a good citizen of the public Overpass instance: requests are cached and this
service should not be hammered in a tight loop (see `settings.external_apis.cache_ttl_s`).
"""

from __future__ import annotations

import httpx

from eclipse_tracker.services.cache import TTLCache
from eclipse_tracker.services.http_retry import with_retries


VIEWPOINT_QUERY_TAGS = (
    'node["tourism"="viewpoint"]',
    'node["natural"="peak"]',
    'node["natural"="beach"]',
    'node["leisure"="park"]',
    'node["tourism"="attraction"]',
    'node["historic"]',
)

FOOD_TAGS = ('node["amenity"="restaurant"]', 'node["amenity"="cafe"]', 'node["amenity"="bar"]')
SIGHTSEEING_TAGS = (
    'node["tourism"="attraction"]',
    'node["tourism"="museum"]',
    'node["historic"]',
    'node["natural"="beach"]',
    'node["tourism"="viewpoint"]',
)


class OverpassQueryError(Exception):
    """Raised when Overpass replies 200 OK but the query itself failed server-side (e.g. its own
    internal `[timeout:N]` budget was exceeded) - it reports this via a `remark` field alongside an
    empty `elements` list rather than a non-2xx status, so it must be checked explicitly."""


class OsmService:
    """Overpass-backed lookups, each result cached by a TTL keyed on the query parameters."""

    def __init__(self, overpass_urls: list[str], user_agent: str, timeout_s: float, cache_ttl_s: float) -> None:
        """Configure the Overpass endpoint(s), request timeout, and result-cache TTL.

        `overpass_urls` is tried in order on each query: public Overpass mirrors are individually
        unreliable (rate limits, outages, and in at least one observed case a mirror resetting the
        TLS handshake for non-browser clients while curl succeeds against it) so a single hardcoded
        URL is a single point of failure for the whole recommendations feature.
        """
        if not overpass_urls:
            msg = "overpass_urls must contain at least one URL"
            raise ValueError(msg)
        self._overpass_urls = overpass_urls
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._cache: TTLCache[list[dict]] = TTLCache(cache_ttl_s)

    async def _run_query(self, query: str, cache_key: str) -> list[dict]:
        async def fetch() -> list[dict]:
            last_error: Exception = OverpassQueryError("no overpass_urls configured")
            for url in self._overpass_urls:
                try:
                    async with httpx.AsyncClient(
                        timeout=self._timeout_s, headers={"User-Agent": self._user_agent}
                    ) as client:
                        response = await client.post(url, data={"data": query})
                        response.raise_for_status()
                        payload = response.json()
                        if "remark" in payload:
                            raise OverpassQueryError(payload["remark"])
                        return payload["elements"]
                except (httpx.HTTPError, OverpassQueryError) as exc:
                    last_error = exc
                    continue
            raise last_error

        return await self._cache.get_or_set(cache_key, lambda: with_retries(fetch))

    async def find_viewpoints_in_bbox(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float, limit: int = 60
    ) -> list[dict]:
        """Real named viewpoint/peak/beach/park/attraction nodes inside a bounding box."""
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        body = "".join(f"{tag}({bbox});" for tag in VIEWPOINT_QUERY_TAGS)
        # 6 unioned tag filters over a range_km-wide bbox (up to 800km) routinely exceeds Overpass's
        # default query budget - give it more room than the small point-radius queries below need.
        query = f"[out:json][timeout:55];({body});out body {limit};"
        cache_key = f"viewpoints:{bbox}:{limit}"
        elements = await self._run_query(query, cache_key)
        return [e for e in elements if e.get("tags", {}).get("name")]

    async def building_count_near(self, lat: float, lon: float, radius_m: float = 150) -> int:
        """Count of OSM building footprints within `radius_m` - a dense-urban-area proxy."""
        query = f'[out:json][timeout:25];(way["building"](around:{radius_m},{lat},{lon}););out ids;'
        cache_key = f"buildings:{lat:.4f},{lon:.4f},{radius_m}"
        elements = await self._run_query(query, cache_key)
        return len(elements)

    async def has_public_access_nearby(self, lat: float, lon: float, radius_m: float = 300) -> tuple[bool, str]:
        """Whether a public road/footpath reaches within `radius_m` (car-or-walking accessibility)."""
        query = (
            "[out:json][timeout:25];"
            f'(way["highway"]["access"!~"private|no"](around:{radius_m},{lat},{lon}););'
            "out ids 1;"
        )
        cache_key = f"access:{lat:.4f},{lon:.4f},{radius_m}"
        elements = await self._run_query(query, cache_key)
        if elements:
            return True, f"Public road/path within {radius_m:.0f} m"
        return False, f"No public road/path found within {radius_m:.0f} m"

    async def find_poi_near(
        self, lat: float, lon: float, radius_m: float, tags: tuple[str, ...], limit: int = 20
    ) -> list[dict]:
        """Named POIs matching `tags` within `radius_m` of a point (food, sightseeing, ...)."""
        body = "".join(f"{tag}(around:{radius_m},{lat},{lon});" for tag in tags)
        query = f"[out:json][timeout:25];({body});out body {limit};"
        cache_key = f"poi:{lat:.4f},{lon:.4f},{radius_m}:{tags}"
        elements = await self._run_query(query, cache_key)
        return [e for e in elements if e.get("tags", {}).get("name")]
