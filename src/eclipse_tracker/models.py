"""Pydantic domain models shared across services and API routers."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EclipseType(StrEnum):
    """Type of solar eclipse."""

    TOTAL = "total"
    ANNULAR = "annular"
    PARTIAL = "partial"
    HYBRID = "hybrid"


class PathPoint(BaseModel):
    """A single sample point on an eclipse's centerline."""

    lat: float
    lon: float
    time_utc: datetime
    totality_duration_s: float = Field(ge=0)
    path_width_km: float = Field(gt=0)
    sun_azimuth_deg: float = Field(ge=0, lt=360)
    sun_altitude_deg: float = Field(ge=-90, le=90)


class Eclipse(BaseModel):
    """A solar eclipse event with its centerline path."""

    id: str
    name: str
    date: str
    type: EclipseType
    source_note: str
    greatest_duration_s: float
    centerline: list[PathPoint]


class ScoreBreakdown(BaseModel):
    """Per-criterion scores (0-100) that make up a candidate's composite score."""

    duration: float
    distance: float
    viewing_angle: float
    beauty: float
    accessibility: float
    composite: float


class Candidate(BaseModel):
    """A scored candidate viewing location."""

    id: str
    name: str
    lat: float
    lon: float
    category: str
    distance_km: float
    totality_duration_s: float
    eclipse_time_utc: datetime
    # Same instant as `eclipse_time_utc`, expressed in the candidate's own civil timezone, plus that
    # zone's IANA name - what a viewer standing there will actually read off their phone.
    eclipse_time_local: datetime
    timezone: str
    sun_azimuth_deg: float
    sun_altitude_deg: float
    horizon_clearance_deg: float
    is_accessible: bool
    accessibility_note: str
    tags: dict[str, str] = Field(default_factory=dict)
    score: ScoreBreakdown


class ScoringWeights(BaseModel):
    """Weights (should sum to ~1.0) used to combine per-criterion scores."""

    duration: float = 0.30
    distance: float = 0.15
    viewing_angle: float = 0.25
    beauty: float = 0.20
    accessibility: float = 0.10


class RecommendationRequest(BaseModel):
    """Request body for POST /api/recommendations."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    range_km: float = Field(gt=0, le=2000, default=100)
    eclipse_id: str | None = None
    limit: int = Field(gt=0, le=100, default=20)
    weights: ScoringWeights | None = None


class RecommendationResponse(BaseModel):
    """Response body for POST /api/recommendations."""

    eclipse: Eclipse
    origin: tuple[float, float]
    range_km: float
    candidates: list[Candidate]
    # Degraded-result notes for the user. An empty `candidates` list is ambiguous on its own -
    # it means either "nowhere in range is under totality" or "the upstream OSM API just failed",
    # and those call for very different reactions.
    warnings: list[str] = Field(default_factory=list)


class ItineraryRequest(BaseModel):
    """Query params for GET /api/itinerary - recomputes local circumstances, no server-side candidate storage."""

    candidate_id: str
    candidate_name: str
    eclipse_id: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ItineraryStop(BaseModel):
    """A single stop in a day itinerary."""

    kind: str
    name: str
    lat: float
    lon: float
    start_local_hint: str
    note: str
    tags: dict[str, str] = Field(default_factory=dict)


class ItineraryResponse(BaseModel):
    """Response body for GET /api/itinerary."""

    candidate_id: str
    eclipse_id: str
    stops: list[ItineraryStop]
