from pytest_bdd import scenario, given, when, then, parsers


@scenario("dummy.feature", "Retrieving a dummy item")
def test_retrieving_a_dummy_item():
    pass


@given(
    parsers.parse('a user requests a dummy item with id "{item_id}"'),
    target_fixture="request_response",
)
def a_user_requests_a_dummy_item_with_id(client, item_id):
    response = client.get(f"/dummy/{item_id}")
    return response


@when("the request is processed")
def the_request_is_processed(request_response):
    assert request_response


@then(parsers.parse('the response should include the message Hello World! with the item id "{item_id}"'))
def the_response_should_include_the_message_with_the_item_id(request_response, item_id):
    assert request_response.status_code == 200
    assert request_response.json() == {"item_id": int(item_id), "message": "Hello World!"}
