"""Endpoints for listing bundled eclipse datasets."""

from fastapi import APIRouter, HTTPException, status

from eclipse_tracker.models import Eclipse
from eclipse_tracker.services import eclipse_service


router = APIRouter(prefix="/api/eclipses", tags=["eclipses"])


@router.get("")
async def list_eclipses() -> list[Eclipse]:
    """List all bundled eclipses."""
    return eclipse_service.list_eclipses()


@router.get("/next")
async def get_next_eclipse() -> Eclipse:
    """Return the soonest upcoming bundled eclipse."""
    return eclipse_service.next_eclipse()


@router.get("/{eclipse_id}")
async def get_eclipse(eclipse_id: str) -> Eclipse:
    """Return a single bundled eclipse by id."""
    try:
        return eclipse_service.get_eclipse(eclipse_id)
    except eclipse_service.EclipseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown eclipse id: {eclipse_id}") from exc
