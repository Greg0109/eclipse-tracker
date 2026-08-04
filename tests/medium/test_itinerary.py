"""Medium tests for the /api/itinerary endpoint, with Overpass mocked via respx."""

from urllib.parse import parse_qs

import respx
from httpx import Response

from eclipse_tracker.config.config import settings


CANDIDATE_LAT, CANDIDATE_LON = 41.9, -4.2  # on the bundled 2026-08-12 centerline
CANDIDATE_NAME = "Test Viewing Spot"


def _poi_node(node_id: int, lat: float, lon: float, name: str, tag_key: str, tag_value: str) -> dict:
    return {"type": "node", "id": node_id, "lat": lat, "lon": lon, "tags": {"name": name, tag_key: tag_value}}


def _overpass_side_effect(request):
    # Food and sightseeing are fetched in a single unioned POI query and split client-side on the
    # amenity tag, so this one response has to carry both categories.
    body = parse_qs(request.content.decode())
    query = body.get("data", [""])[0]
    assert "amenity" in query, query
    assert "tourism" in query, query

    return Response(
        200,
        json={
            "elements": [
                _poi_node(2, CANDIDATE_LAT, CANDIDATE_LON, "Museo del Eclipse", "tourism", "museum"),
                _poi_node(1, CANDIDATE_LAT, CANDIDATE_LON, "Restaurante Sol", "amenity", "restaurant"),
            ]
        },
    )


def _empty_overpass_side_effect(_request):
    return Response(200, json={"elements": []})


def _itinerary_params(**overrides) -> dict:
    params = {
        "candidate_id": "cand-1",
        "candidate_name": CANDIDATE_NAME,
        "eclipse_id": "2026-08-12",
        "lat": CANDIDATE_LAT,
        "lon": CANDIDATE_LON,
    }
    params.update(overrides)
    return params


@respx.mock
def test_itinerary_returns_arrival_sightseeing_and_food_stops(client):
    respx.post(settings.external_apis.overpass_urls[0]).mock(side_effect=_overpass_side_effect)

    response = client.get("/api/itinerary", params=_itinerary_params())

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == "cand-1"
    assert body["eclipse_id"] == "2026-08-12"
    kinds = [stop["kind"] for stop in body["stops"]]
    assert kinds[0] == "arrival"
    assert "sightseeing" in kinds
    assert "food" in kinds
    assert "eclipse" in kinds

    sightseeing_stop = next(stop for stop in body["stops"] if stop["kind"] == "sightseeing")
    assert sightseeing_stop["name"] == "Museo del Eclipse"
    food_stop = next(stop for stop in body["stops"] if stop["kind"] == "food")
    assert food_stop["name"] == "Restaurante Sol"


@respx.mock
def test_itinerary_with_no_nearby_pois_still_returns_arrival_and_eclipse_stops(client):
    respx.post(settings.external_apis.overpass_urls[0]).mock(side_effect=_empty_overpass_side_effect)

    response = client.get("/api/itinerary", params=_itinerary_params())

    assert response.status_code == 200
    kinds = [stop["kind"] for stop in response.json()["stops"]]
    assert kinds == ["arrival", "eclipse"]


@respx.mock
def test_itinerary_unknown_eclipse_id_is_404(client):
    response = client.get("/api/itinerary", params=_itinerary_params(eclipse_id="nope"))
    assert response.status_code == 404
