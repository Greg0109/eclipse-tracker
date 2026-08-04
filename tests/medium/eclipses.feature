Feature: Eclipse listing endpoints

  Scenario: Listing all bundled eclipses
    Given a user requests the list of eclipses
    When the request is processed
    Then the response should include the 2026-08-12 eclipse

  Scenario: Fetching the next eclipse
    Given a user requests the next eclipse
    When the request is processed
    Then the response should include the 2026-08-12 eclipse

  Scenario: Fetching an unknown eclipse
    Given a user requests the eclipse with id "does-not-exist"
    When the request is processed
    Then the response should be a 404
