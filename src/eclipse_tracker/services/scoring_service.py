"""
Pure scoring logic: combines raw per-candidate signals into a weighted 0-100 composite.

No I/O here - callers (recommendation_service) gather the raw signals from eclipse,
terrain and OSM data first, then hand them to `score_candidate`. Kept pure and dependency
free so it is trivially unit-testable.
"""

from __future__ import annotations

from eclipse_tracker.models import ScoreBreakdown, ScoringWeights


BEAUTY_WEIGHT_BY_CATEGORY = {
    "viewpoint": 95,
    "peak": 100,
    "beach": 90,
    "attraction": 75,
    "historic": 70,
    "park": 65,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def duration_score(totality_duration_s: float, greatest_duration_s: float) -> float:
    """Longer totality relative to this eclipse's global maximum scores higher."""
    if greatest_duration_s <= 0:
        return 0.0
    return _clamp(100 * totality_duration_s / greatest_duration_s)


def distance_score(distance_km: float, range_km: float) -> float:
    """Closer to the user (within their chosen range) scores higher."""
    if range_km <= 0:
        return 0.0
    return _clamp(100 * (1 - distance_km / range_km))


def viewing_angle_score(horizon_clearance_deg: float, full_score_clearance_deg: float = 15.0) -> float:
    """
    Degrees of clearance between the sun's altitude and the local terrain horizon.
    Zero or negative clearance (terrain at/above the sun) scores 0; clearance at or
    beyond `full_score_clearance_deg` scores 100.
    """
    if horizon_clearance_deg <= 0:
        return 0.0
    return _clamp(100 * horizon_clearance_deg / full_score_clearance_deg)


def beauty_score(category: str, building_count_nearby: int) -> float:
    """Scenic-ness heuristic: OSM category base score, penalized for dense urban surroundings."""
    base = BEAUTY_WEIGHT_BY_CATEGORY.get(category, 55)
    density_penalty = _clamp(building_count_nearby * 1.5, 0, 40)
    return _clamp(base - density_penalty)


def accessibility_score(is_accessible: bool) -> float:
    """Binary hard-signal expressed as a score for consistent weighting/display."""
    return 100.0 if is_accessible else 0.0


def score_candidate(
    *,
    totality_duration_s: float,
    greatest_duration_s: float,
    distance_km: float,
    range_km: float,
    horizon_clearance_deg: float,
    category: str,
    building_count_nearby: int,
    is_accessible: bool,
    weights: ScoringWeights | None = None,
) -> ScoreBreakdown:
    """Compute the full per-criterion + weighted composite score for one candidate."""
    weights = weights or ScoringWeights()

    duration = duration_score(totality_duration_s, greatest_duration_s)
    distance = distance_score(distance_km, range_km)
    viewing_angle = viewing_angle_score(horizon_clearance_deg)
    beauty = beauty_score(category, building_count_nearby)
    accessibility = accessibility_score(is_accessible)

    composite = (
        duration * weights.duration
        + distance * weights.distance
        + viewing_angle * weights.viewing_angle
        + beauty * weights.beauty
        + accessibility * weights.accessibility
    )

    return ScoreBreakdown(
        duration=round(duration, 1),
        distance=round(distance, 1),
        viewing_angle=round(viewing_angle, 1),
        beauty=round(beauty, 1),
        accessibility=round(accessibility, 1),
        composite=round(composite, 1),
    )
