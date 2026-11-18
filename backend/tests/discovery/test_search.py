from sqlalchemy import select

from app.models import Item, SearchLog
from tests.discovery.helpers import item, names, request, search, world


def test_dorm_items_never_leak_to_other_dorms(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Handheld vacuum", "dorm", category="dorm")
    assert names(search(client, w.wilbur2, "vacuum")) == ["Handheld vacuum"]
    assert names(search(client, w.flomo, "vacuum")) == []
    assert names(search(client, w.flomo, "")) == []  # browse too
    assert names(search(client, w.flomo, "vacuum", available_only="false")) == []


def test_group_items_only_for_members(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Soldering iron", "groups", group_ids=[w.group_id], category="tech")
    assert names(search(client, w.wilbur2, "soldering iron")) == []
    assert names(search(client, w.flomo, "soldering iron")) == []
    client.post(f"/api/communities/{w.group_id}/join", headers=w.flomo, json={})
    assert names(search(client, w.flomo, "soldering iron")) == ["Soldering iron"]
    assert names(search(client, w.flomo, "", community_id=w.group_id)) == ["Soldering iron"]


def test_private_items_never_in_search(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Bike pump", "private", category="sports")
    for viewer in (w.wilbur2, w.flomo, w.wilbur):
        assert names(search(client, viewer, "bike pump")) == []
        assert names(search(client, viewer, "")) == []


def test_own_items_excluded_and_status_filters(client, db):
    w = world(client, db)
    a = item(client, w.wilbur, "Desk lamp", category="dorm")
    item(client, w.wilbur, "Desk fan", category="dorm")
    assert names(search(client, w.wilbur, "desk")) == []
    db.execute(Item.__table__.update().where(Item.id == a["id"]).values(status="borrowed"))
    db.commit()
    assert "Desk lamp" not in names(search(client, w.flomo, "desk lamp"))
    assert "Desk lamp" in names(search(client, w.flomo, "desk lamp", available_only="false"))
    db.execute(Item.__table__.update().where(Item.id == a["id"]).values(status="unavailable"))
    db.commit()
    assert "Desk lamp" not in names(search(client, w.flomo, "desk lamp", available_only="false"))
    assert client.delete(f"/api/items/{a['id']}", headers=w.wilbur).status_code in (204, 409)


def test_explicit_filters(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Graphing calculator", category="academic", condition="good")
    item(client, w.wilbur, "Calculator watch", category="tech", condition="worn")
    item(client, w.wilbur, "Free calculator", category="academic", transaction_type="give")
    r = search(client, w.flomo, "calculator", category="tech")
    assert names(r) == ["Calculator watch"]
    assert names(search(client, w.flomo, "calculator", condition="good")) == ["Graphing calculator"]
    assert names(search(client, w.flomo, "calculator", transaction_type="give")) == [
        "Free calculator"
    ]
    assert names(search(client, w.flomo, "free calculator")) == ["Free calculator"]


def test_scope_dorm_and_walking_distance(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Wilbur kettle", category="dorm")
    item(client, w.flomo, "FloMo kettle", category="dorm")
    assert names(search(client, w.wilbur2, "kettle in my dorm")) == ["Wilbur kettle"]
    assert names(search(client, w.wilbur2, "kettle", scope="dorm")) == ["Wilbur kettle"]
    both = names(search(client, w.wilbur2, "kettle"))
    assert both[0] == "Wilbur kettle" and set(both) == {"Wilbur kettle", "FloMo kettle"}
    assert names(search(client, w.wilbur2, "kettle", max_walk_min=1)) == ["Wilbur kettle"]


def test_results_have_match_info_and_browse_has_no_score(client, db):
    w = world(client, db)
    item(client, w.wilbur, "Yoga mat", category="sports")
    r = search(client, w.wilbur2, "yoga mat")
    card = r["items"][0]
    assert card["match_score"] is not None and "Same dorm" in card["match_reason"]
    browse = search(client, w.wilbur2, "")
    assert browse["items"][0]["match_score"] is None


def test_requests_and_communities_in_search(client, db):
    w = world(client, db)
    request(client, w.flomo, "anyone have a tent for the weekend?", title="Tent", category="sports")
    r = search(client, w.wilbur, "tent")
    assert [x["title"] for x in r["requests"]] == ["Tent"]
    assert [x["title"] for x in search(client, w.flomo, "tent")["requests"]] == []  # own
    c = search(client, w.flomo, "robotics", kind="communities")
    assert [x["name"] for x in c["communities"]] == ["Robotics"]
    assert search(client, w.flomo, "100%_", kind="communities")["communities"] == []


def test_pagination_and_logging(client, db):
    w = world(client, db)
    for i in range(7):
        item(client, w.wilbur, f"Notebook {i}", category="academic")
    p1 = search(client, w.flomo, "notebook", limit=5)
    assert len(p1["items"]) == 5 and p1["next_offset"] == 5
    p2 = search(client, w.flomo, "notebook", limit=5, offset=5)
    assert len(p2["items"]) == 2 and p2["next_offset"] is None
    assert not {i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}
    logs = db.scalars(select(SearchLog)).all()
    assert len(logs) == 2 and logs[0].raw_query == "notebook" and len(logs[0].result_item_ids) == 5


def test_bad_params(client, db):
    w = world(client, db)
    for params in (
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
        {"kind": "users"},
        {"category": "nope"},
        {"q": "x" * 501},
    ):
        assert client.get("/api/search", headers=w.flomo, params=params).status_code == 422
    assert client.get("/api/search", params={"q": "x"}).status_code == 401
