"""Small tests for lat/lon -> civil timezone resolution."""

from datetime import UTC, datetime

import pytest

from eclipse_tracker.services import timezone_service


ECLIPSE_MOMENT = datetime(2026, 8, 12, 18, 31, tzinfo=UTC)


@pytest.mark.parametrize(
    ("lat", "lon", "expected_zone"),
    [
        (41.9, -4.2, "Europe/Madrid"),  # Spain leg of the 2026 path
        (64.1, -21.9, "Atlantic/Reykjavik"),  # Iceland leg
        (51.5, -0.13, "Europe/London"),
    ],
)
def test_timezone_name_resolves_by_coordinates(lat, lon, expected_zone):
    assert timezone_service.timezone_name(lat, lon) == expected_zone


def test_to_local_shifts_the_same_instant_into_the_local_zone():
    local = timezone_service.to_local(ECLIPSE_MOMENT, 41.9, -4.2)

    assert local.hour == 20  # CEST is UTC+2 in August
    assert local.timestamp() == ECLIPSE_MOMENT.timestamp()


def test_format_local_labels_the_zone():
    assert timezone_service.format_local(ECLIPSE_MOMENT, 41.9, -4.2) == "20:31 CEST"
    assert timezone_service.format_local(ECLIPSE_MOMENT, 64.1, -21.9) == "18:31 GMT"


def test_open_ocean_falls_back_to_utc():
    assert timezone_service.timezone_name(0.0, -160.0) in {"UTC", "Etc/GMT+11"}
