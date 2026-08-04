"""Builds a simple day-of timeline around a chosen viewing location and eclipse time."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from eclipse_tracker.models import Eclipse, ItineraryResponse, ItineraryStop
from eclipse_tracker.services import eclipse_service, timezone_service
from eclipse_tracker.services.osm_service import FOOD_TAGS, SIGHTSEEING_TAGS, OsmService


if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime


FOOD_AMENITIES = frozenset({"restaurant", "cafe", "bar"})

ARRIVAL_BUFFER = timedelta(hours=2)
MORNING_STOP_OFFSET = timedelta(hours=4)
LUNCH_OFFSET = timedelta(hours=2, minutes=30)
DINNER_OFFSET = timedelta(hours=1)
POI_SEARCH_RADIUS_M = 6000


def _pick(elements: list[dict], exclude_name: str, exclude_ids: Collection[int] = ()) -> dict | None:
    for element in elements:
        name = element.get("tags", {}).get("name")
        if name and name != exclude_name and element.get("id") not in exclude_ids:
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

    # One Overpass round-trip for both categories, split locally on the amenity tag: public
    # instances rate-limit concurrent requests, so two queries here cost far more than one.
    pois = await osm.find_poi_near(lat, lon, POI_SEARCH_RADIUS_M, SIGHTSEEING_TAGS + FOOD_TAGS, limit=40)
    food = [poi for poi in pois if poi.get("tags", {}).get("amenity") in FOOD_AMENITIES]
    sightseeing = [poi for poi in pois if poi.get("tags", {}).get("amenity") not in FOOD_AMENITIES]

    eclipse_time = circumstances.time_utc
    # Each stop is paired with the time it happens at so the timeline can be emitted in
    # chronological order - the stops are *built* in narrative order (arrival, then the optional
    # ones, then totality), which is not the order a reader should see them in.
    planned: list[tuple[datetime, ItineraryStop]] = []

    def plan(when: datetime, stop: ItineraryStop) -> None:
        planned.append((when, stop))

    arrival_time = eclipse_time - ARRIVAL_BUFFER
    plan(
        arrival_time,
        ItineraryStop(
            kind="arrival",
            name=candidate_name,
            lat=lat,
            lon=lon,
            start_local_hint=timezone_service.format_local(arrival_time, lat, lon),
            note="Arrive early to secure parking/space - popular viewing spots fill up before totality.",
        ),
    )

    morning_sightseeing = _pick(sightseeing, candidate_name)
    if morning_sightseeing:
        sightseeing_time = eclipse_time - MORNING_STOP_OFFSET
        plan(
            sightseeing_time,
            _stop_from_element(
                morning_sightseeing,
                "sightseeing",
                timezone_service.format_local(sightseeing_time, lat, lon),
                "While you wait: nearby sightseeing before heading to your viewing spot.",
            ),
        )

    lunch = _pick(food, candidate_name)
    if lunch:
        lunch_time = eclipse_time - LUNCH_OFFSET
        plan(
            lunch_time,
            _stop_from_element(
                lunch,
                "food",
                timezone_service.format_local(lunch_time, lat, lon),
                "Grab a meal before settling in for the eclipse.",
            ),
        )

    plan(
        eclipse_time,
        ItineraryStop(
            kind="eclipse",
            name=candidate_name,
            lat=lat,
            lon=lon,
            start_local_hint=timezone_service.format_local(eclipse_time, lat, lon),
            note=(
                f"Totality: ~{circumstances.totality_duration_s:.0f}s, "
                f"sun altitude {circumstances.sun_altitude_deg:.0f} deg."
            ),
        ),
    )

    # A different venue than lunch, otherwise the day reads as eating at the same place twice.
    dinner = _pick(food, candidate_name, exclude_ids={lunch["id"]} if lunch else frozenset())
    if dinner:
        dinner_time = eclipse_time + DINNER_OFFSET
        plan(
            dinner_time,
            _stop_from_element(
                dinner,
                "food",
                timezone_service.format_local(dinner_time, lat, lon),
                "Celebrate afterwards with a bite nearby.",
            ),
        )

    planned.sort(key=lambda item: item[0])
    return ItineraryResponse(candidate_id=candidate_id, eclipse_id=eclipse_id, stops=[stop for _, stop in planned])
