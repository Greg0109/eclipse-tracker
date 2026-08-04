from eclipse_tracker.services.poi_classify import classify


def test_classify_viewpoint():
    assert classify({"tourism": "viewpoint"}) == "viewpoint"


def test_classify_peak():
    assert classify({"natural": "peak"}) == "peak"


def test_classify_beach():
    assert classify({"natural": "beach"}) == "beach"


def test_classify_park():
    assert classify({"leisure": "park"}) == "park"


def test_classify_historic():
    assert classify({"historic": "monument"}) == "historic"


def test_classify_attraction():
    assert classify({"tourism": "attraction"}) == "attraction"


def test_classify_unknown_tags_fall_back_to_poi():
    assert classify({"shop": "bakery"}) == "poi"
