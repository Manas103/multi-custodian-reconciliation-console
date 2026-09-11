import json

from app.lambda_handler import handler


def test_handler_returns_summary_and_exceptions():
    resp = handler({"seed": 20260910})
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["accounts"] == 500
    assert body["records"] == 250000
    assert body["seeded_breaks_caught"] == body["seeded_breaks_total"] == 40
    assert body["false_holds"] == 0
    assert len(body["exceptions"]) == 40
    for exc in body["exceptions"]:
        assert exc["rule"] in {"timing", "quantity", "price", "missing", "duplicate"}
        assert exc["disagreeing_field"]


def test_handler_default_seed_when_event_not_a_dict():
    resp = handler(None)
    assert resp["statusCode"] == 200
