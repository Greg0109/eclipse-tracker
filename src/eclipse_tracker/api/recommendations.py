"""Endpoint that ranks candidate eclipse-viewing locations for a given origin/range."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eclipse_tracker.dependencies import get_osm_service, get_terrain_service
from eclipse_tracker.models import RecommendationRequest, RecommendationResponse
from eclipse_tracker.services import eclipse_service
from eclipse_tracker.services.osm_service import OsmService
from eclipse_tracker.services.recommendation_service import recommend
from eclipse_tracker.services.terrain_service import TerrainService


router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("")
async def post_recommendations(
    request: RecommendationRequest,
    osm: Annotated[OsmService, Depends(get_osm_service)],
    terrain: Annotated[TerrainService, Depends(get_terrain_service)],
) -> RecommendationResponse:
    """Rank real, publicly-accessible viewing locations within `range_km` of (lat, lon)."""
    try:
        return await recommend(
            lat=request.lat,
            lon=request.lon,
            range_km=request.range_km,
            eclipse_id=request.eclipse_id,
            limit=request.limit,
            weights=request.weights,
            osm=osm,
            terrain=terrain,
        )
    except eclipse_service.EclipseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown eclipse id: {request.eclipse_id}"
        ) from exc
