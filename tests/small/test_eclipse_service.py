from datetime import UTC, datetime

from eclipse_tracker.services import eclipse_service


def test_list_eclipses_includes_bundled_2026_eclipse():
    eclipses = eclipse_service.list_eclipses()
    assert any(e.id == "2026-08-12" for e in eclipses)


def test_get_eclipse_by_id():
    eclipse = eclipse_service.get_eclipse("2026-08-12")
    assert eclipse.type == "total"
    assert len(eclipse.centerline) > 1


def test_get_eclipse_unknown_id_raises():
    try:
        eclipse_service.get_eclipse("does-not-exist")
    except eclipse_service.EclipseNotFoundError:
        pass
    else:
        raise AssertionError("expected EclipseNotFoundError")


def test_next_eclipse_before_event_returns_it():
    eclipse = eclipse_service.next_eclipse(now=datetime(2026, 1, 1, tzinfo=UTC))
    assert eclipse.id == "2026-08-12"


def test_local_circumstances_at_a_centerline_point_matches_it():
    eclipse = eclipse_service.get_eclipse("2026-08-12")
    sample = eclipse.centerline[8]
    circumstances = eclipse_service.local_circumstances(eclipse, sample.lat, sample.lon)
    assert abs(circumstances.totality_duration_s - sample.totality_duration_s) < 0.01


def test_local_circumstances_interpolates_between_points():
    eclipse = eclipse_service.get_eclipse("2026-08-12")
    a, b = eclipse.centerline[8], eclipse.centerline[9]
    mid_lat = (a.lat + b.lat) / 2
    mid_lon = (a.lon + b.lon) / 2
    circumstances = eclipse_service.local_circumstances(eclipse, mid_lat, mid_lon)
    low, high = sorted((a.totality_duration_s, b.totality_duration_s))
    assert low <= circumstances.totality_duration_s <= high


def test_is_in_totality_path_true_on_centerline():
    eclipse = eclipse_service.get_eclipse("2026-08-12")
    sample = eclipse.centerline[8]
    assert eclipse_service.is_in_totality_path(eclipse, sample.lat, sample.lon)


def test_is_in_totality_path_false_far_away():
    eclipse = eclipse_service.get_eclipse("2026-08-12")
    assert not eclipse_service.is_in_totality_path(eclipse, 10.0, 10.0)
