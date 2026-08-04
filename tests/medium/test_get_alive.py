"""check service is alive feature tests."""

from pytest_bdd import scenario, then, when


@scenario("get_alive.feature", "service is indeed alive")
def test_service_is_indeed_alive():
    """service is indeed alive."""


@when("user requests if service is alive", target_fixture="alive_response")
def _(session):
    """user requests if service is alive."""

    alive_response = session.get("/alive")
    return alive_response


@then("returns service version")
def _(alive_response):
    """returns service version."""
    assert alive_response


@then("service is alive")
def _(alive_response):
    """service is alive."""
    assert alive_response
