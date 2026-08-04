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

from eclipse_tracker.logging_setup import get_logger
from eclipse_tracker.services.cache import TTLCache
from eclipse_tracker.services.http_retry import with_retries


logger = get_logger(__name__)


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
        hedge_delay_s: float = 10.0,
    ) -> None:
        """Configure the Overpass endpoint(s), request timeout, result-cache TTL and request budget.

        `overpass_urls` is raced with a staggered start on each query: public Overpass mirrors are
        individually unreliable (rate limits, outages, and in at least one observed case a mirror
        resetting the TLS handshake for non-browser clients while curl succeeds against it) so a
        single hardcoded URL is a single point of failure for the whole recommendations feature.
        List them fastest-when-healthy first; `hedge_delay_s` is how long each gets before the next
        is also started.

        `max_concurrent_requests` caps in-flight Overpass queries; public instances hand out only a
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
        self._hedge_delay_s = hedge_delay_s
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._cache: TTLCache[list[dict]] = TTLCache(cache_ttl_s)
        self._count_cache: TTLCache[int] = TTLCache(cache_ttl_s)

    async def _post(self, url: str, query: str) -> list[dict]:
        """POST `query` to one mirror and return its elements, or raise."""
        async with httpx.AsyncClient(timeout=self._timeout_s, headers={"User-Agent": self._user_agent}) as client:
            response = await client.post(url, data={"data": query})
            response.raise_for_status()
            payload = response.json()
            if "remark" in payload:
                raise OverpassQueryError(payload["remark"])
            return payload["elements"]

    async def _race_mirrors(self, query: str) -> list[dict]:
        """Send `query` to the mirrors with a staggered start and take the first success.

        Trying mirrors strictly in series means one slow instance costs its full timeout before the
        next is even attempted, which is how a single query ends up taking minutes. Instead each
        mirror gets `hedge_delay_s` to answer before the next one is also started; whichever replies
        first wins and the rest are cancelled. A mirror that fails fast (unreachable, rate-limited)
        advances the stagger immediately rather than after the delay.
        """
        pending: set[asyncio.Task[list[dict]]] = set()
        remaining = list(self._overpass_urls)
        last_error: Exception = OverpassQueryError("no overpass_urls configured")

        try:
            while True:
                if remaining:
                    pending.add(asyncio.create_task(self._post(remaining.pop(0), query)))
                if not pending:
                    raise last_error

                done, pending = await asyncio.wait(
                    pending,
                    timeout=self._hedge_delay_s if remaining else None,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    error = task.exception()
                    if error is None:
                        return task.result()
                    # ValueError also covers a mirror answering 200 with an HTML rate-limit page,
                    # which fails JSON decoding rather than raising an httpx error.
                    if not isinstance(error, httpx.HTTPError | OverpassQueryError | ValueError):
                        raise error
                    last_error = error
        finally:
            for task in pending:
                task.cancel()

    async def _execute(self, query: str) -> list[dict]:
        """Run `query` against the mirrors, with retries. Not cached."""
        async with self._semaphore:
            return await with_retries(lambda: self._race_mirrors(query))

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
        """Find real named viewpoint/peak/beach/park/attraction nodes inside a bounding box.

        One request *per tag* rather than one unioned request for all of them. Overpass evaluates a
        union in full before applying `out body N`, so over a range_km-wide bbox the union routinely
        blew its own `[timeout:55]` budget (`node["natural"="peak"]` alone matches >10k nodes). The
        per-tag queries each finish in a few seconds, are cached separately, and one failing tag
        costs its own results instead of the whole search.
        """
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        per_tag_limit = max(1, limit // len(VIEWPOINT_QUERY_TAGS) * 2)

        async def for_tag(tag: str) -> list[dict]:
            query = f"[out:json][timeout:50];({tag}({bbox}););out body {per_tag_limit};"
            return await self._run_query(query, f"viewpoints:{bbox}:{tag}:{per_tag_limit}")

        results = await asyncio.gather(*(for_tag(tag) for tag in VIEWPOINT_QUERY_TAGS), return_exceptions=True)

        by_id: dict[tuple[str, int], dict] = {}
        for tag, result in zip(VIEWPOINT_QUERY_TAGS, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("overpass_viewpoint_tag_failed", tag=tag, error=str(result))
                continue
            for element in result:
                if element.get("tags", {}).get("name"):
                    by_id[(element["type"], element["id"])] = element

        return list(by_id.values())[:limit]

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
