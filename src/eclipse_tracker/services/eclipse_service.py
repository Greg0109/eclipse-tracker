"""Loads bundled eclipse datasets and interpolates local circumstances along their centerlines."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from eclipse_tracker.models import Eclipse, PathPoint
from eclipse_tracker.services.geo import haversine_km, nearest_point_on_polyline


DATA_DIR = Path(__file__).parent.parent / "data" / "eclipses"


class EclipseNotFoundError(Exception):
    """Raised when a requested eclipse id does not exist in the bundled datasets."""


@lru_cache
def _load_all() -> tuple[Eclipse, ...]:
    eclipses = [
        Eclipse.model_validate(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(DATA_DIR.glob("*.json"))
    ]
    return tuple(sorted(eclipses, key=lambda e: e.date))


def list_eclipses() -> list[Eclipse]:
    """All bundled eclipses, sorted by date."""
    return list(_load_all())


def get_eclipse(eclipse_id: str) -> Eclipse:
    """Return a single bundled eclipse by id."""
    for eclipse in _load_all():
        if eclipse.id == eclipse_id:
            return eclipse
    raise EclipseNotFoundError(eclipse_id)


def next_eclipse(now: datetime | None = None) -> Eclipse:
    """Return the soonest upcoming bundled eclipse (or the most recent one if all are in the past)."""
    now = now or datetime.now(UTC)
    upcoming = [e for e in _load_all() if datetime.fromisoformat(e.date).replace(tzinfo=UTC) >= now]
    if upcoming:
        return upcoming[0]
    return _load_all()[-1]


def local_circumstances(eclipse: Eclipse, lat: float, lon: float) -> PathPoint:
    """
    Interpolated eclipse circumstances (time, duration, sun position) at an arbitrary
    lat/lon, projected onto the nearest segment of the eclipse's centerline.

    This is a linear interpolation between the two bracketing bundled sample points -
    adequate given how closely spaced the bundled centerline samples are, but it is an
    approximation, not a re-derivation of the true umbral geometry at that exact point.
    """
    polyline = [(p.lat, p.lon) for p in eclipse.centerline]
    idx, frac = nearest_point_on_polyline(lat, lon, polyline)
    a, b = eclipse.centerline[idx], eclipse.centerline[idx + 1]

    def lerp(x: float, y: float) -> float:
        return x + frac * (y - x)

    time_utc = a.time_utc + (b.time_utc - a.time_utc) * frac

    return PathPoint(
        lat=lat,
        lon=lon,
        time_utc=time_utc,
        totality_duration_s=lerp(a.totality_duration_s, b.totality_duration_s),
        path_width_km=lerp(a.path_width_km, b.path_width_km),
        sun_azimuth_deg=lerp(a.sun_azimuth_deg, b.sun_azimuth_deg),
        sun_altitude_deg=lerp(a.sun_altitude_deg, b.sun_altitude_deg),
    )


def distance_to_centerline_km(eclipse: Eclipse, lat: float, lon: float) -> float:
    """Perpendicular-ish distance (km) from (lat, lon) to the eclipse's centerline."""
    polyline = [(p.lat, p.lon) for p in eclipse.centerline]
    idx, frac = nearest_point_on_polyline(lat, lon, polyline)
    a, b = polyline[idx], polyline[idx + 1]
    proj_lat = a[0] + frac * (b[0] - a[0])
    proj_lon = a[1] + frac * (b[1] - a[1])
    return haversine_km(lat, lon, proj_lat, proj_lon)


def is_in_totality_path(eclipse: Eclipse, lat: float, lon: float) -> bool:
    """Whether (lat, lon) falls within the (approximate) path-of-totality corridor."""
    circumstances = local_circumstances(eclipse, lat, lon)
    return distance_to_centerline_km(eclipse, lat, lon) <= circumstances.path_width_km / 2
