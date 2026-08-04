"""Resolves the civil timezone at a lat/lon so eclipse times can be shown in local time.

Eclipse circumstances are computed and stored in UTC, but "totality at 18:31 UTC" is not what a
person standing in Spain (20:31 CEST) or Iceland (18:31 GMT) needs to read. Lookups are offline
(`timezonefinder` ships its own boundary data), so this adds no network dependency.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timezonefinder import TimezoneFinder


if TYPE_CHECKING:
    from datetime import datetime


UTC = ZoneInfo("UTC")


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    """Return the shared TimezoneFinder; constructing it loads boundary data, so do it once."""
    return TimezoneFinder()


@lru_cache(maxsize=4096)
def timezone_at(lat: float, lon: float) -> ZoneInfo:
    """Return the civil timezone at a point, falling back to UTC out at sea or on unknown zones."""
    name = _finder().timezone_at(lat=lat, lng=lon)
    if not name:
        return UTC
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        return UTC


def timezone_name(lat: float, lon: float) -> str:
    """Return the IANA name of the timezone at a point, e.g. `Europe/Madrid`."""
    return timezone_at(lat, lon).key


def to_local(moment: datetime, lat: float, lon: float) -> datetime:
    """Convert an aware UTC datetime to the civil local time at a point."""
    return moment.astimezone(timezone_at(lat, lon))


def format_local(moment: datetime, lat: float, lon: float) -> str:
    """Format a UTC datetime as local wall-clock time with its zone abbreviation, e.g. `20:31 CEST`."""
    local = to_local(moment, lat, lon)
    return f"{local:%H:%M} {local.tzname() or 'UTC'}".strip()
