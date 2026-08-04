"""
OpenStreetMap data access via the public Overpass API.

Used for three things:
  1. Finding real, named, publicly-reachable candidate viewing spots (viewpoints, peaks,
     beaches, parks, attractions) instead of scoring arbitrary lat/lon grid points.
  2. A cheap urban-obstruction / accessibility proxy: building density and nearby roads.
  3. Points of interest (restaurants, cafes, sightseeing) to build a day itinerary.

Public Overpass instances are slow (tens of seconds for a wide bbox query), heavily rate
limited (a couple of concurrent slots per IP) and individually unreliable. Everything here is
therefore built around *minimising request count* rather than parallelising it:

  - point-radius lookups for many candidates are batched into a single query using repeated
    `out count;` statements, whose results come back in statement order;
  - a semaphore caps how many Overpass requests are ever in flight at once;
  - every result is TTL-cached (see `settings.external_apis.cache_ttl_s`);
  - `overpass_urls` is tried in order, so one dead mirror degrades latency instead of the feature.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx

from eclipse_tracker.services.cache import TTLCache
from eclipse_tracker.services.http_retry import with_retries


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence


# Every clause carries ["name"] because unnamed elements are discarded client-side anyway, and
# pushing that filter into the query is what keeps a wide-bbox union inside Overpass's own
# `[timeout:N]` budget - node["natural"="peak"] alone matches >10k nodes over a 300 km box.
VIEWPOINT_QUERY_TAGS = (
    'node["tourism"="viewpoint"]["name"]',
    'node["natural"="peak"]["name"]',
    'node["natural"="beach"]["name"]',
    'node["leisure"="park"]["name"]',
    'node["tourism"="attraction"]["name"]',
    'node["historic"]["name"]',
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
    empty `elements` list rather than a non-2xx status, so it must be checked explicitly.
    """


class OsmService:
    """Overpass-backed lookups, each result cached by a TTL keyed on the query parameters."""

    def __init__(
        self,
        overpass_urls: list[str],
        user_agent: str,
        timeout_s: float,
        cache_ttl_s: float,
        *,
        max_concurrent_requests: int = 2,
        batch_size: int = 15,
    ) -> None:
        """Configure the Overpass endpoint(s), request timeout, result-cache TTL and request budget.

        `overpass_urls` is tried in order on each query: public Overpass mirrors are individually
        unreliable (rate limits, outages, and in at least one observed case a mirror resetting the
        TLS handshake for non-browser clients while curl succeeds against it) so a single hardcoded
        URL is a single point of failure for the whole recommendations feature.

        `max_concurrent_requests` caps in-flight Overpass requests; public instances hand out only a
        couple of slots per client and answer the rest with 429 or an HTML error page.
        `batch_size` is how many point-radius lookups get folded into one batched query.
        """
        if not overpass_urls:
            msg = "overpass_urls must contain at least one URL"
            raise ValueError(msg)
        self._overpass_urls = overpass_urls
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._cache: TTLCache[list[dict]] = TTLCache(cache_ttl_s)
        self._count_cache: TTLCache[int] = TTLCache(cache_ttl_s)

    async def _post(self, url: str, query: str) -> list[dict]:
        """POST `query` to one mirror and return its elements, or raise."""
        async with (
            self._semaphore,
            httpx.AsyncClient(timeout=self._timeout_s, headers={"User-Agent": self._user_agent}) as client,
        ):
            response = await client.post(url, data={"data": query})
            response.raise_for_status()
            payload = response.json()
            if "remark" in payload:
                raise OverpassQueryError(payload["remark"])
            return payload["elements"]

    async def _execute(self, query: str) -> list[dict]:
        """POST `query` to the first mirror that answers, with retries. Not cached."""

        async def fetch() -> list[dict]:
            last_error: Exception = OverpassQueryError("no overpass_urls configured")
            for url in self._overpass_urls:
                try:
                    return await self._post(url, query)
                except (httpx.HTTPError, OverpassQueryError, ValueError) as exc:
                    # ValueError also covers a mirror answering 200 with an HTML rate-limit page,
                    # which fails JSON decoding rather than raising an httpx error.
                    last_error = exc
                    continue
            raise last_error

        return await with_retries(fetch)

    async def _run_query(self, query: str, cache_key: str) -> list[dict]:
        return await self._cache.get_or_set(cache_key, lambda: self._execute(query))

    async def _batched_counts(
        self, points: Sequence[tuple[float, float]], statement: Callable[[float, float], str], cache_prefix: str
    ) -> list[int]:
        """Resolve one count per point, folding cache misses into as few Overpass queries as possible.

        Overpass returns one `{"type": "count"}` element per `out count;` statement, in statement
        order, so N point-radius lookups cost one request instead of N.
        """
        keys = [f"{cache_prefix}:{lat:.4f},{lon:.4f}" for lat, lon in points]
        counts: dict[int, int] = {}
        missing: list[int] = []
        for i, key in enumerate(keys):
            cached = self._count_cache.get(key)
            if cached is None:
                missing.append(i)
            else:
                counts[i] = cached

        for start in range(0, len(missing), self._batch_size):
            chunk = missing[start : start + self._batch_size]
            body = "".join(f"{statement(*points[i])}out count;" for i in chunk)
            elements = await self._execute(f"[out:json][timeout:60];{body}")
            totals = [int(e["tags"]["total"]) for e in elements if e.get("type") == "count"]
            if len(totals) != len(chunk):
                msg = f"expected {len(chunk)} count results from Overpass, got {len(totals)}"
                raise OverpassQueryError(msg)
            for i, total in zip(chunk, totals, strict=True):
                counts[i] = total
                self._count_cache.set(keys[i], total)

        return [counts[i] for i in range(len(points))]

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

    async def building_counts_near(self, points: Sequence[tuple[float, float]], radius_m: float = 150) -> list[int]:
        """Count OSM building footprints within `radius_m` of each point - a dense-urban-area proxy."""

        def statement(lat: float, lon: float) -> str:
            return f'way["building"](around:{radius_m},{lat},{lon});'

        return await self._batched_counts(points, statement, f"buildings:{radius_m}")

    async def public_access_near(
        self, points: Sequence[tuple[float, float]], radius_m: float = 300
    ) -> list[tuple[bool, str]]:
        """Report whether a public road/footpath reaches within `radius_m` of each point."""

        def statement(lat: float, lon: float) -> str:
            return f'way["highway"]["access"!~"private|no"](around:{radius_m},{lat},{lon});'

        counts = await self._batched_counts(points, statement, f"access:{radius_m}")
        reachable = f"Public road/path within {radius_m:.0f} m"
        unreachable = f"No public road/path found within {radius_m:.0f} m"
        return [(count > 0, reachable if count > 0 else unreachable) for count in counts]

    async def find_poi_near(
        self, lat: float, lon: float, radius_m: float, tags: Iterable[str], limit: int = 20
    ) -> list[dict]:
        """Find named POIs matching `tags` within `radius_m` of a point (food, sightseeing, ...)."""
        tags = tuple(tags)
        body = "".join(f"{tag}(around:{radius_m},{lat},{lon});" for tag in tags)
        query = f"[out:json][timeout:25];({body});out body {limit};"
        cache_key = f"poi:{lat:.4f},{lon:.4f},{radius_m}:{tags}"
        elements = await self._run_query(query, cache_key)
        return [e for e in elements if e.get("tags", {}).get("name")]
