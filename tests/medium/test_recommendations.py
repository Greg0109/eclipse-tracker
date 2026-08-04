"""Medium tests for the /api/recommendations endpoint, with Overpass/Open-Elevation mocked via respx."""

from urllib.parse import parse_qs

import respx
from httpx import Response

from eclipse_tracker.config.config import settings


CANDIDATE_LAT, CANDIDATE_LON = 41.9, -4.2  # on the bundled 2026-08-12 centerline


def _viewpoint_node(node_id: int, lat: float, lon: float, name: str) -> dict:
    return {"type": "node", "id": node_id, "lat": lat, "lon": lon, "tags": {"name": name, "tourism": "viewpoint"}}


def _count_elements(query: str, total: int) -> dict:
    """One `{"type": "count"}` element per `out count;` statement, as Overpass returns them."""
    return {"elements": [{"type": "count", "id": 0, "tags": {"total": str(total)}}] * query.count("out count;")}


def _overpass_side_effect(request):
    body = parse_qs(request.content.decode())
    query = body.get("data", [""])[0]

    if "around" not in query:
        return Response(200, json={"elements": [_viewpoint_node(1, CANDIDATE_LAT, CANDIDATE_LON, "Mirador del Eclipse")]})
    if "building" in query:
        return Response(200, json=_count_elements(query, 1))
    if "access" in query:
        return Response(200, json=_count_elements(query, 1))
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
def test_recommendations_warns_when_overpass_is_unreachable(client):
    """An empty candidate list must not be silent about an upstream outage."""
    # Every mirror, not just the first: a failing mirror is hedged onto the next one.
    for url in settings.external_apis.overpass_urls:
        respx.post(url).mock(return_value=Response(504))
    respx.get(settings.external_apis.elevation_url).mock(side_effect=_elevation_side_effect)

    response = client.post(
        "/api/recommendations",
        json={"lat": CANDIDATE_LAT, "lon": CANDIDATE_LON, "range_km": 50, "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"] == []
    assert len(body["warnings"]) == 1
    assert "Overpass" in body["warnings"][0]


@respx.mock
def test_recommendations_survive_a_rate_limited_elevation_service(client):
    """Open-Elevation 429s must degrade the terrain score, not silently delete the candidate."""
    respx.post(settings.external_apis.overpass_urls[0]).mock(side_effect=_overpass_side_effect)
    respx.get(settings.external_apis.elevation_url).mock(return_value=Response(429))

    response = client.post(
        "/api/recommendations",
        json={"lat": CANDIDATE_LAT, "lon": CANDIDATE_LON, "range_km": 50, "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["name"] == "Mirador del Eclipse"
    assert any("flat horizon" in warning for warning in body["warnings"])


@respx.mock
def test_recommendations_reports_no_warnings_on_the_happy_path(client):
    respx.post(settings.external_apis.overpass_urls[0]).mock(side_effect=_overpass_side_effect)
    respx.get(settings.external_apis.elevation_url).mock(side_effect=_elevation_side_effect)

    response = client.post(
        "/api/recommendations",
        json={"lat": CANDIDATE_LAT, "lon": CANDIDATE_LON, "range_km": 50, "limit": 5},
    )

    assert response.json()["warnings"] == []


@respx.mock
def test_recommendations_unknown_eclipse_id_is_404(client):
    response = client.post(
        "/api/recommendations",
        json={"lat": CANDIDATE_LAT, "lon": CANDIDATE_LON, "range_km": 50, "eclipse_id": "nope"},
    )
    assert response.status_code == 404
