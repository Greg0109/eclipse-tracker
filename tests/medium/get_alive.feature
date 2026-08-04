Feature: check service is alive

    All services must have a way to check if they are working correctly.
    This is typically done with an alive endpoint.
    This feature is defined just to enable executable specifications

    Scenario: service is indeed alive
        When user requests if service is alive
        Then service is alive
        And returns service version