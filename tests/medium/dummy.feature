Feature: Dummy Functionality

  Scenario: Retrieving a dummy item
    Given a user requests a dummy item with id "42"
    When the request is processed
    Then the response should include the message Hello World! with the item id "42"
