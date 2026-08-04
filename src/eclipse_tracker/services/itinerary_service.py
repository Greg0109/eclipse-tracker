"""Builds a simple day-of timeline around a chosen viewing location and eclipse time."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from eclipse_tracker.models import Eclipse, ItineraryResponse, ItineraryStop
from eclipse_tracker.services import eclipse_service
from eclipse_tracker.services.osm_service import FOOD_TAGS, SIGHTSEEING_TAGS, OsmService


ARRIVAL_BUFFER = timedelta(hours=2)
MORNING_STOP_OFFSET = timedelta(hours=4)
EVENING_STOP_OFFSET = timedelta(hours=1, minutes=30)
POI_SEARCH_RADIUS_M = 6000


def _pick(elements: list[dict], exclude_name: str) -> dict | None:
    for element in elements:
        name = element.get("tags", {}).get("name")
        if name and name != exclude_name:
            return element
    return None


def _stop_from_element(element: dict, kind: str, start_hint: str, note: str) -> ItineraryStop:
    tags = element.get("tags", {})
    return ItineraryStop(
        kind=kind,
        name=tags["name"],
        lat=element["lat"],
        lon=element["lon"],
        start_local_hint=start_hint,
        note=note,
        tags={k: v for k, v in tags.items() if k != "name"},
    )


async def build_itinerary(
    *,
    candidate_id: str,
    candidate_name: str,
    eclipse_id: str,
    lat: float,
    lon: float,
    osm: OsmService,
) -> ItineraryResponse:
    """Fetch nearby food/sightseeing and lay out a simple day-of timeline around totality."""
    eclipse: Eclipse = eclipse_service.get_eclipse(eclipse_id)
    circumstances = eclipse_service.local_circumstances(eclipse, lat, lon)

    sightseeing, food = await asyncio.gather(
        osm.find_poi_near(lat, lon, POI_SEARCH_RADIUS_M, SIGHTSEEING_TAGS),
        osm.find_poi_near(lat, lon, POI_SEARCH_RADIUS_M, FOOD_TAGS),
    )

    eclipse_time = circumstances.time_utc
    stops: list[ItineraryStop] = [
        ItineraryStop(
            kind="arrival",
            name=candidate_name,
            lat=lat,
            lon=lon,
            start_local_hint=(eclipse_time - ARRIVAL_BUFFER).strftime("%H:%M UTC"),
            note="Arrive early to secure parking/space - popular viewing spots fill up before totality.",
        )
    ]

    morning_sightseeing = _pick(sightseeing, candidate_name)
    if morning_sightseeing:
        stops.append(
            _stop_from_element(
                morning_sightseeing,
                "sightseeing",
                (eclipse_time - MORNING_STOP_OFFSET).strftime("%H:%M UTC"),
                "While you wait: nearby sightseeing before heading to your viewing spot.",
            )
        )

    lunch = _pick(food, candidate_name)
    if lunch:
        stops.append(
            _stop_from_element(
                lunch,
                "food",
                (eclipse_time - EVENING_STOP_OFFSET - timedelta(hours=1)).strftime("%H:%M UTC"),
                "Grab a meal before settling in for the eclipse.",
            )
        )

    stops.append(
        ItineraryStop(
            kind="eclipse",
            name=candidate_name,
            lat=lat,
            lon=lon,
            start_local_hint=eclipse_time.strftime("%H:%M UTC"),
            note=(
                f"Totality: ~{circumstances.totality_duration_s:.0f}s, "
                f"sun altitude {circumstances.sun_altitude_deg:.0f} deg."
            ),
        )
    )

    dinner = _pick(food, candidate_name)
    if dinner and (not lunch or dinner.get("id") != lunch.get("id")):
        stops.append(
            _stop_from_element(
                dinner,
                "food",
                (eclipse_time + timedelta(hours=1)).strftime("%H:%M UTC"),
                "Celebrate afterwards with a bite nearby.",
            )
        )

    return ItineraryResponse(candidate_id=candidate_id, eclipse_id=eclipse_id, stops=stops)
