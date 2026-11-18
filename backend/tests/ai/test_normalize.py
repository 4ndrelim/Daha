import pytest

from app.ai.normalize import extract_json, normalize_items, payload_from_text


def test_extract_plain():
    assert extract_json('{"items": []}') == {"items": []}


def test_extract_fenced():
    assert extract_json('```json\n{"items": [{"name": "Lamp"}]}\n```')["items"][0]["name"] == "Lamp"


def test_extract_wrapped_in_prose():
    text = 'Here is what I found:\n{"items": [{"name": "Desk lamp"}]}\nHope that helps!'
    assert extract_json(text)["items"][0]["name"] == "Desk lamp"


@pytest.mark.parametrize("text", ["", "no json here", "{not json}", '["a list"]', "{'single': 1}"])
def test_extract_invalid(text):
    with pytest.raises(ValueError):
        extract_json(text)


def test_payload_requires_items_list():
    with pytest.raises(ValueError):
        payload_from_text('{"things": []}')


def test_normalize_clamps_and_maps():
    items = normalize_items(
        [
            {
                "name": "  Desk   lamp ",
                "category": "LIGHTING",
                "confidence": 7,
                "quantity": "3",
                "bbox": [0.9, 0.9, 0.5, 0.5],
                "condition_guess": "like new",
                "suggested_transaction_type": "free",
            },
            {"name": "Desk lamp", "quantity": 2},  # duplicate → merged
            {
                "name": "Bike repair help",
                "category": "services",
                "suggested_transaction_type": "lend",
            },
            {"name": "Student ID card"},  # never listed
            {"name": "Car keys"},
            {"name": "Toothbrush", "suggested_share": True},  # forced unticked
            {"name": ""},
            "garbage",
        ]
    )
    names = [i.name for i in items]
    assert names == ["Desk lamp", "Bike repair help", "Toothbrush"]
    lamp, service, brush = items
    assert lamp.category == "other" and lamp.confidence == 1.0 and lamp.quantity == 5
    assert lamp.condition_guess == "like_new" and lamp.suggested_transaction_type == "give"
    assert lamp.bbox == [0.9, 0.9, 0.1, 0.1]
    assert service.suggested_transaction_type == "give"
    assert brush.suggested_share is False and brush.sensitive_reason


def test_normalize_caps_at_20():
    assert len(normalize_items([{"name": f"Thing {i}"} for i in range(40)])) == 20


def test_ring_binder_is_not_jewelry():
    (binder,) = normalize_items([{"name": "Black 3-ring binder"}])
    assert binder.suggested_share is True
