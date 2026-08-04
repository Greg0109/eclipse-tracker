from eclipse_tracker.models import ScoringWeights
from eclipse_tracker.services import scoring_service


def test_duration_score_at_maximum_is_100():
    assert scoring_service.duration_score(120, 120) == 100


def test_duration_score_half_of_maximum_is_50():
    assert scoring_service.duration_score(60, 120) == 50


def test_duration_score_zero_max_is_zero():
    assert scoring_service.duration_score(60, 0) == 0


def test_distance_score_at_origin_is_100():
    assert scoring_service.distance_score(0, 100) == 100


def test_distance_score_at_range_edge_is_zero():
    assert scoring_service.distance_score(100, 100) == 0


def test_viewing_angle_score_blocked_is_zero():
    assert scoring_service.viewing_angle_score(0) == 0
    assert scoring_service.viewing_angle_score(-5) == 0


def test_viewing_angle_score_clear_horizon_is_full():
    assert scoring_service.viewing_angle_score(20, full_score_clearance_deg=15) == 100


def test_beauty_score_peak_beats_generic_poi():
    assert scoring_service.beauty_score("peak", 0) > scoring_service.beauty_score("poi", 0)


def test_beauty_score_penalizes_dense_buildings():
    assert scoring_service.beauty_score("viewpoint", 0) > scoring_service.beauty_score("viewpoint", 30)


def test_accessibility_score_binary():
    assert scoring_service.accessibility_score(True) == 100
    assert scoring_service.accessibility_score(False) == 0


def test_score_candidate_composite_uses_weights():
    weights = ScoringWeights(duration=1, distance=0, viewing_angle=0, beauty=0, accessibility=0)
    result = scoring_service.score_candidate(
        totality_duration_s=120,
        greatest_duration_s=120,
        distance_km=50,
        range_km=100,
        horizon_clearance_deg=10,
        category="peak",
        building_count_nearby=0,
        is_accessible=True,
        weights=weights,
    )
    assert result.composite == 100


def test_score_candidate_blocked_view_drags_composite_down():
    blocked = scoring_service.score_candidate(
        totality_duration_s=120,
        greatest_duration_s=120,
        distance_km=10,
        range_km=100,
        horizon_clearance_deg=-2,
        category="viewpoint",
        building_count_nearby=0,
        is_accessible=True,
    )
    clear = scoring_service.score_candidate(
        totality_duration_s=120,
        greatest_duration_s=120,
        distance_km=10,
        range_km=100,
        horizon_clearance_deg=20,
        category="viewpoint",
        building_count_nearby=0,
        is_accessible=True,
    )
    assert blocked.composite < clear.composite
