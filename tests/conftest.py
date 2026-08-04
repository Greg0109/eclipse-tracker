"""Configuration for pytest."""

from fastapi.testclient import TestClient
import pytest

from eclipse_tracker.app import app


@pytest.fixture(scope="session")
def session():
    """Session fixture."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client
