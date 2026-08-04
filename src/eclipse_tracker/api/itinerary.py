"""Endpoint that builds a day-of itinerary around a chosen viewing location."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eclipse_tracker.dependencies import get_osm_service
from eclipse_tracker.models import ItineraryResponse
from eclipse_tracker.services import eclipse_service
from eclipse_tracker.services.itinerary_service import build_itinerary
from eclipse_tracker.services.osm_service import OsmService


router = APIRouter(prefix="/api/itinerary", tags=["itinerary"])


@router.get("")
async def get_itinerary(
    osm: Annotated[OsmService, Depends(get_osm_service)],
    *,
    candidate_id: Annotated[str, Query()],
    candidate_name: Annotated[str, Query()],
    eclipse_id: Annotated[str, Query()],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> ItineraryResponse:
    """Build a simple day-of timeline (arrival, food, sightseeing, totality) around a candidate."""
    try:
        return await build_itinerary(
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            eclipse_id=eclipse_id,
            lat=lat,
            lon=lon,
            osm=osm,
        )
    except eclipse_service.EclipseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown eclipse id: {eclipse_id}") from exc
