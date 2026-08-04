from pytest_bdd import given, scenario, then, parsers, when


@scenario("eclipses.feature", "Listing all bundled eclipses")
def test_listing_all_bundled_eclipses():
    pass


@scenario("eclipses.feature", "Fetching the next eclipse")
def test_fetching_the_next_eclipse():
    pass


@scenario("eclipses.feature", "Fetching an unknown eclipse")
def test_fetching_an_unknown_eclipse():
    pass


@given("a user requests the list of eclipses", target_fixture="request_response")
def request_eclipse_list(client):
    return client.get("/api/eclipses")


@given("a user requests the next eclipse", target_fixture="request_response")
def request_next_eclipse(client):
    return client.get("/api/eclipses/next")


@given(parsers.parse('a user requests the eclipse with id "{eclipse_id}"'), target_fixture="request_response")
def request_eclipse_by_id(client, eclipse_id):
    return client.get(f"/api/eclipses/{eclipse_id}")


@when("the request is processed")
def the_request_is_processed(request_response):
    assert request_response


@then("the response should include the 2026-08-12 eclipse")
def response_includes_2026_eclipse(request_response):
    assert request_response.status_code == 200
    body = request_response.json()
    ids = [e["id"] for e in body] if isinstance(body, list) else [body["id"]]
    assert "2026-08-12" in ids


@then("the response should be a 404")
def response_is_404(request_response):
    assert request_response.status_code == 404
