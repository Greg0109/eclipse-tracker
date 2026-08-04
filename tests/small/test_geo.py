import math

from eclipse_tracker.services import geo


def test_haversine_km_same_point_is_zero():
    assert geo.haversine_km(41.65, -0.9, 41.65, -0.9) == 0


def test_haversine_km_known_distance():
    # Madrid to Barcelona, roughly 500 km.
    distance = geo.haversine_km(40.4168, -3.7038, 41.3851, 2.1734)
    assert 490 < distance < 510


def test_initial_bearing_due_east():
    bearing = geo.initial_bearing_deg(0, 0, 0, 10)
    assert math.isclose(bearing, 90, abs_tol=0.5)


def test_initial_bearing_due_north():
    bearing = geo.initial_bearing_deg(0, 0, 10, 0)
    assert math.isclose(bearing, 0, abs_tol=0.5)


def test_destination_point_round_trip_distance():
    lat, lon = geo.destination_point(41.65, -0.9, 90, 50)
    distance = geo.haversine_km(41.65, -0.9, lat, lon)
    assert math.isclose(distance, 50, abs_tol=0.5)
    assert (lat, lon) != (41.65, -0.9)


def test_is_within_range():
    assert geo.is_within_range(41.65, -0.9, 41.66, -0.91, range_km=5)
    assert not geo.is_within_range(41.65, -0.9, 42.65, -0.9, range_km=5)


def test_bounding_box_contains_center():
    min_lat, min_lon, max_lat, max_lon = geo.bounding_box(41.65, -0.9, 50)
    assert min_lat < 41.65 < max_lat
    assert min_lon < -0.9 < max_lon


def test_nearest_point_on_polyline_projects_onto_segment():
    polyline = [(0.0, 0.0), (0.0, 10.0)]
    idx, frac = geo.nearest_point_on_polyline(0.0, 5.0, polyline)
    assert idx == 0
    assert math.isclose(frac, 0.5, abs_tol=0.01)


def test_nearest_point_on_polyline_clamps_to_segment_ends():
    polyline = [(0.0, 0.0), (0.0, 10.0)]
    idx, frac = geo.nearest_point_on_polyline(0.0, -5.0, polyline)
    assert idx == 0
    assert frac == 0.0
