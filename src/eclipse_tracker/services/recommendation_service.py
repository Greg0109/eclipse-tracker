"""Orchestrates eclipse, terrain and OSM lookups into ranked candidate viewing locations."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx

from eclipse_tracker.logging_setup import get_logger
from eclipse_tracker.models import Candidate, Eclipse, RecommendationResponse, ScoringWeights
from eclipse_tracker.services import eclipse_service
from eclipse_tracker.services.geo import bounding_box, haversine_km
from eclipse_tracker.services.osm_service import OverpassQueryError
from eclipse_tracker.services.poi_classify import classify
from eclipse_tracker.services.scoring_service import score_candidate


logger = get_logger(__name__)


if TYPE_CHECKING:
    from eclipse_tracker.services.osm_service import OsmService
    from eclipse_tracker.services.terrain_service import TerrainService


async def _build_candidate(
    element: dict,
    *,
    eclipse: Eclipse,
    origin_lat: float,
    origin_lon: float,
    range_km: float,
    weights: ScoringWeights,
    osm: OsmService,
    terrain: TerrainService,
) -> Candidate | None:
    lat, lon = element["lat"], element["lon"]
    tags = element.get("tags", {})
    name = tags.get("name")
    if not name:
        return None

    distance_km = haversine_km(origin_lat, origin_lon, lat, lon)
    if distance_km > range_km:
        return None

    if not eclipse_service.is_in_totality_path(eclipse, lat, lon):
        return None

    circumstances = eclipse_service.local_circumstances(eclipse, lat, lon)

    try:
        clearance, building_count, (is_accessible, access_note) = await asyncio.gather(
            terrain.horizon_clearance_deg(lat, lon, circumstances.sun_azimuth_deg, circumstances.sun_altitude_deg),
            osm.building_count_near(lat, lon),
            osm.has_public_access_nearby(lat, lon),
        )
    except (httpx.HTTPError, OverpassQueryError):
        # A flaky public API (Open-Elevation/Overpass) shouldn't sink the whole recommendation
        # request - drop this one candidate and keep the rest.
        return None

    category = classify(tags)
    score = score_candidate(
        totality_duration_s=circumstances.totality_duration_s,
        greatest_duration_s=eclipse.greatest_duration_s,
        distance_km=distance_km,
        range_km=range_km,
        horizon_clearance_deg=clearance,
        category=category,
        building_count_nearby=building_count,
        is_accessible=is_accessible,
        weights=weights,
    )

    return Candidate(
        id=f"{element['type']}/{element['id']}",
        name=name,
        lat=lat,
        lon=lon,
        category=category,
        distance_km=round(distance_km, 2),
        totality_duration_s=round(circumstances.totality_duration_s, 1),
        eclipse_time_utc=circumstances.time_utc,
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

    candidates = await asyncio.gather(
        *(
            _build_candidate(
                element,
                eclipse=eclipse,
                origin_lat=lat,
                origin_lon=lon,
                range_km=range_km,
                weights=weights,
                osm=osm,
                terrain=terrain,
            )
            for element in elements
        )
    )

    ranked = sorted((c for c in candidates if c is not None), key=lambda c: c.score.composite, reverse=True)

    return RecommendationResponse(
        eclipse=eclipse,
        origin=(lat, lon),
        range_km=range_km,
        candidates=ranked[:limit],
    )
