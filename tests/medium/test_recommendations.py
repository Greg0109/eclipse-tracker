"""Medium tests for the /api/recommendations endpoint, with Overpass/Open-Elevation mocked via respx."""

from urllib.parse import parse_qs

import respx
from httpx import Response

from eclipse_tracker.config.config import settings


CANDIDATE_LAT, CANDIDATE_LON = 41.9, -4.2  # on the bundled 2026-08-12 centerline


def _viewpoint_node(node_id: int, lat: float, lon: float, name: str) -> dict:
    return {"type": "node", "id": node_id, "lat": lat, "lon": lon, "tags": {"name": name, "tourism": "viewpoint"}}


def _overpass_side_effect(request):
    body = parse_qs(request.content.decode())
    query = body.get("data", [""])[0]

    if "around" not in query:
        return Response(200, json={"elements": [_viewpoint_node(1, CANDIDATE_LAT, CANDIDATE_LON, "Mirador del Eclipse")]})
    if "building" in query:
        return Response(200, json={"elements": [{"type": "way", "id": 10}]})
    if "access" in query:
        return Response(200, json={"elements": [{"type": "way", "id": 20}]})
    if "amenity" in query:
        return Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 30,
                        "lat": CANDIDATE_LAT,
                        "lon": CANDIDATE_LON,
                        "tags": {"name": "Restaurante Sol", "amenity": "restaurant"},
                    }
                ]
            },
        )
    return Response(200, json={"elements": []})


def _elevation_side_effect(request):
    locations = request.url.params["locations"].split("|")
    return Response(200, json={"results": [{"elevation": 500.0} for _ in locations]})


@respx.mock
def test_recommendations_returns_ranked_real_candidate(client):
    respx.post(settings.external_apis.overpass_urls[0]).mock(side_effect=_overpass_side_effect)
    respx.get(settings.external_apis.elevation_url).mock(side_effect=_elevation_side_effect)

    response = client.post(
        "/api/recommendations",
        json={"lat": CANDIDATE_LAT, "lon": CANDIDATE_LON, "range_km": 50, "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["eclipse"]["id"] == "2026-08-12"
    assert len(body["candidates"]) == 1
    candidate = body["candidates"][0]
    assert candidate["name"] == "Mirador del Eclipse"
    assert candidate["category"] == "viewpoint"
    assert candidate["is_accessible"] is True
    assert 0 <= candidate["score"]["composite"] <= 100


@respx.mock
def test_recommendations_out_of_range_origin_returns_no_candidates(client):
    respx.post(settings.external_apis.overpass_urls[0]).mock(side_effect=_overpass_side_effect)
    respx.get(settings.external_apis.elevation_url).mock(side_effect=_elevation_side_effect)

    response = client.post(
        "/api/recommendations",
        json={"lat": 0.0, "lon": 0.0, "range_km": 10, "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["candidates"] == []


@respx.mock
def test_recommendations_unknown_eclipse_id_is_404(client):
    response = client.post(
        "/api/recommendations",
        json={"lat": CANDIDATE_LAT, "lon": CANDIDATE_LON, "range_km": 50, "eclipse_id": "nope"},
    )
    assert response.status_code == 404
