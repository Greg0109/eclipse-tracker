from eclipse_tracker.app import say


def test_say():
    assert say() == "Hello World!"
