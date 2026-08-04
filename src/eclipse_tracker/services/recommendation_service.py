"""Orchestrates eclipse, terrain and OSM lookups into ranked candidate viewing locations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from eclipse_tracker.logging_setup import get_logger
from eclipse_tracker.models import Candidate, RecommendationResponse, ScoringWeights
from eclipse_tracker.services import eclipse_service, timezone_service
from eclipse_tracker.services.geo import bounding_box, haversine_km
from eclipse_tracker.services.osm_service import OverpassQueryError
from eclipse_tracker.services.poi_classify import classify
from eclipse_tracker.services.scoring_service import score_candidate


logger = get_logger(__name__)


if TYPE_CHECKING:
    from eclipse_tracker.models import Eclipse, PathPoint
    from eclipse_tracker.services.osm_service import OsmService
    from eclipse_tracker.services.terrain_service import TerrainService


# Each surviving candidate costs one Open-Elevation request, and contributes one statement to each
# of the two batched Overpass queries. A wide bbox can return 60 in-path viewpoints; enriching all
# of them makes the request take minutes against public API rate limits. Rank cheaply first (the
# eclipse maths is pure and local), then only pay for the ones that can plausibly make the top of
# the list.
MAX_ENRICHED_CANDIDATES = 15


@dataclass(frozen=True)
class _Prospect:
    """An in-path OSM element with its locally-computed eclipse circumstances, before enrichment."""

    element: dict
    lat: float
    lon: float
    distance_km: float
    circumstances: PathPoint


def _prospects(
    elements: list[dict], *, eclipse: Eclipse, origin_lat: float, origin_lon: float, range_km: float
) -> list[_Prospect]:
    """Keep the named, in-range, in-totality elements and attach their local circumstances.

    Pure and local - no network - so this is the cheap filter that runs before enrichment.
    """
    prospects = []
    for element in elements:
        lat, lon = element["lat"], element["lon"]
        if not element.get("tags", {}).get("name"):
            continue
        distance_km = haversine_km(origin_lat, origin_lon, lat, lon)
        if distance_km > range_km or not eclipse_service.is_in_totality_path(eclipse, lat, lon):
            continue
        prospects.append(
            _Prospect(
                element=element,
                lat=lat,
                lon=lon,
                distance_km=distance_km,
                circumstances=eclipse_service.local_circumstances(eclipse, lat, lon),
            )
        )
    return prospects


def _preliminary_rank(prospect: _Prospect, range_km: float) -> float:
    """Score a prospect on the duration/distance signals alone, to pick who is worth enriching."""
    duration_ratio = prospect.circumstances.totality_duration_s / 300.0
    closeness = 1.0 - min(prospect.distance_km / range_km, 1.0) if range_km else 0.0
    return duration_ratio + 0.5 * closeness


async def _clearance_or_none(terrain: TerrainService, prospect: _Prospect) -> float | None:
    """Horizon clearance for one prospect, or None if Open-Elevation failed for it."""
    try:
        return await terrain.horizon_clearance_deg(
            prospect.lat,
            prospect.lon,
            prospect.circumstances.sun_azimuth_deg,
            prospect.circumstances.sun_altitude_deg,
        )
    except httpx.HTTPError as exc:
        # A flaky public API shouldn't sink the whole request - drop this one candidate.
        logger.warning("elevation_lookup_failed", lat=prospect.lat, lon=prospect.lon, error=str(exc))
        return None


def _to_candidate(
    prospect: _Prospect,
    *,
    eclipse: Eclipse,
    range_km: float,
    weights: ScoringWeights,
    clearance: float,
    building_count: int,
    access: tuple[bool, str],
) -> Candidate:
    element = prospect.element
    tags = element["tags"]
    circumstances = prospect.circumstances
    category = classify(tags)
    is_accessible, access_note = access

    score = score_candidate(
        totality_duration_s=circumstances.totality_duration_s,
        greatest_duration_s=eclipse.greatest_duration_s,
        distance_km=prospect.distance_km,
        range_km=range_km,
        horizon_clearance_deg=clearance,
        category=category,
        building_count_nearby=building_count,
        is_accessible=is_accessible,
        weights=weights,
    )

    return Candidate(
        id=f"{element['type']}/{element['id']}",
        name=tags["name"],
        lat=prospect.lat,
        lon=prospect.lon,
        category=category,
        distance_km=round(prospect.distance_km, 2),
        totality_duration_s=round(circumstances.totality_duration_s, 1),
        eclipse_time_utc=circumstances.time_utc,
        eclipse_time_local=timezone_service.to_local(circumstances.time_utc, prospect.lat, prospect.lon),
        timezone=timezone_service.timezone_name(prospect.lat, prospect.lon),
        sun_azimuth_deg=round(circumstances.sun_azimuth_deg, 1),
        sun_altitude_deg=round(circumstances.sun_altitude_deg, 1),
        horizon_clearance_deg=round(clearance, 1),
        is_accessible=is_accessible,
        accessibility_note=access_note,
        tags={k: v for k, v in tags.items() if k != "name"},
        score=score,
    )


async def recommend(
    *,
    lat: float,
    lon: float,
    range_km: float,
    eclipse_id: str | None,
    limit: int,
    weights: ScoringWeights | None,
    osm: OsmService,
    terrain: TerrainService,
) -> RecommendationResponse:
    """Rank real, accessible OSM-known locations within range_km along the eclipse path."""
    eclipse = eclipse_service.get_eclipse(eclipse_id) if eclipse_id else eclipse_service.next_eclipse()
    weights = weights or ScoringWeights()

    min_lat, min_lon, max_lat, max_lon = bounding_box(lat, lon, range_km)
    try:
        elements = await osm.find_viewpoints_in_bbox(min_lat, min_lon, max_lat, max_lon)
    except (httpx.HTTPError, OverpassQueryError) as exc:
        # Overpass being unreachable/rate-limited/overloaded shouldn't 500 the whole request -
        # degrade to no candidates, but log it since this failure mode is otherwise silent to the user.
        logger.warning("overpass_viewpoint_query_failed", error=str(exc))
        elements = []

    prospects = _prospects(elements, eclipse=eclipse, origin_lat=lat, origin_lon=lon, range_km=range_km)
    prospects.sort(key=lambda p: _preliminary_rank(p, range_km), reverse=True)
    prospects = prospects[:MAX_ENRICHED_CANDIDATES]
    if not prospects:
        return RecommendationResponse(eclipse=eclipse, origin=(lat, lon), range_km=range_km, candidates=[])

    points = [(p.lat, p.lon) for p in prospects]
    try:
        building_counts, access = await asyncio.gather(
            osm.building_counts_near(points),
            osm.public_access_near(points),
        )
    except (httpx.HTTPError, OverpassQueryError) as exc:
        # The candidates are still real and rankable without the urban/accessibility signals;
        # fall back to neutral values rather than returning an empty list.
        logger.warning("overpass_candidate_enrichment_failed", error=str(exc))
        building_counts = [0] * len(prospects)
        access = [(True, "Accessibility unknown - Overpass lookup unavailable")] * len(prospects)

    clearances = await asyncio.gather(*(_clearance_or_none(terrain, p) for p in prospects))

    candidates = [
        _to_candidate(
            prospect,
            eclipse=eclipse,
            range_km=range_km,
            weights=weights,
            clearance=clearance,
            building_count=building_count,
            access=candidate_access,
        )
        for prospect, clearance, building_count, candidate_access in zip(
            prospects, clearances, building_counts, access, strict=True
        )
        if clearance is not None
    ]

    ranked = sorted(candidates, key=lambda c: c.score.composite, reverse=True)
    return RecommendationResponse(eclipse=eclipse, origin=(lat, lon), range_km=range_km, candidates=ranked[:limit])
