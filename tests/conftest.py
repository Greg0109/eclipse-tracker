"""Configuration for pytest."""

from fastapi.testclient import TestClient
import pytest

from eclipse_tracker.app import app
from eclipse_tracker.dependencies import get_osm_service, get_terrain_service


@pytest.fixture(scope="session")
def session():
    """Session fixture."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def _clear_service_singletons():
    """Prevent the OSM/terrain TTL caches from leaking results between tests (plan §6.1)."""
    get_osm_service.cache_clear()
    get_terrain_service.cache_clear()
    yield
    get_osm_service.cache_clear()
    get_terrain_service.cache_clear()
