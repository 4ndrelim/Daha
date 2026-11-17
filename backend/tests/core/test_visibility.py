"""The visibility matrix (PLAN.md §7.4).

campus / dorm / groups / private × owner / member / outsider, for items and requests.
"""

import pytest
from sqlalchemy import select

from app.models import Item, ItemRequest, User
from app.services.viewer import build_viewer
from app.services.visibility import (
    item_visible_clause,
    request_visible_clause,
    user_can_view_request,
)
from tests.core.factories import community_id, make_item, make_request, seed_base, signup


@pytest.fixture
def world(client, db):
    seed_base(db)
    wilbur, flomo = community_id(db, "wilbur"), community_id(db, "flomo")
    campus = community_id(db, "campus")
    owner_h, owner = signup(client, "Owner", dorm_id=wilbur)
    mate_h, mate = signup(client, "Dormmate", dorm_id=wilbur)
    out_h, outsider = signup(client, "Outsider", dorm_id=flomo)
    group = client.post(
        "/api/communities",
        json={"name": "Robotics Club", "group_type": "club", "is_private": False},
        headers=owner_h,
    ).json()
    # the outsider (different dorm) is in the group with the owner
    assert client.post(f"/api/communities/{group['id']}/join", headers=out_h).status_code == 200
    return {
        "campus": campus,
        "wilbur": wilbur,
        "group": group["id"],
        "owner": owner,
        "mate": mate,
        "outsider": outsider,
        "headers": {"owner": owner_h, "mate": mate_h, "outsider": out_h},
    }


# visibility → who can see it (owner always can)
MATRIX = {
    "campus": {"owner": True, "mate": True, "outsider": True},
    "dorm": {"owner": True, "mate": True, "outsider": False},
    "groups": {"owner": True, "mate": False, "outsider": True},
    "private": {"owner": True, "mate": False, "outsider": False},
}


def _audience(world, visibility):
    return {
        "campus": [world["campus"]],
        "dorm": [world["wilbur"]],
        "groups": [world["group"]],
        "private": [],
    }[visibility]


@pytest.mark.parametrize("visibility", list(MATRIX))
def test_item_visibility_matrix(db, client, world, visibility):
    item = make_item(db, world["owner"]["id"], visibility, _audience(world, visibility))
    for who, expected in MATRIX[visibility].items():
        viewer = build_viewer(db, db.get(User, world[who]["id"]))
        seen = db.scalars(select(Item.id).where(item_visible_clause(viewer))).all()
        assert (item.id in seen) is expected, f"{visibility} item, viewer={who}"

        # the profile endpoint agrees — except private items never show on a profile
        listed = client.get(
            f"/api/users/{world['owner']['id']}/items", headers=world["headers"][who]
        ).json()["items"]
        on_profile = expected and visibility != "private"
        assert (item.id in [i["id"] for i in listed]) is on_profile


@pytest.mark.parametrize("visibility", list(MATRIX))
def test_request_visibility_matrix(db, world, visibility):
    req = make_request(db, world["owner"]["id"], visibility, _audience(world, visibility))
    for who, expected in MATRIX[visibility].items():
        viewer = build_viewer(db, db.get(User, world[who]["id"]))
        seen = db.scalars(select(ItemRequest.id).where(request_visible_clause(viewer))).all()
        assert (req.id in seen) is expected, f"{visibility} request, viewer={who}"
        assert user_can_view_request(db, world[who]["id"], req.id) is expected


def test_archived_items_are_hidden_from_everyone_in_discovery(db, world):
    item = make_item(db, world["owner"]["id"], "campus", [world["campus"]], archived=True)
    for who in ("owner", "mate", "outsider"):
        viewer = build_viewer(db, db.get(User, world[who]["id"]))
        assert item.id not in db.scalars(select(Item.id).where(item_visible_clause(viewer))).all()


def test_item_card_fields(db, client, world):
    make_item(db, world["owner"]["id"], "dorm", [world["wilbur"]], name="Vacuum", category="dorm")
    cards = client.get(
        f"/api/users/{world['owner']['id']}/items", headers=world["headers"]["mate"]
    ).json()["items"]
    assert len(cards) == 1
    card = cards[0]
    assert card["community_label"] == "Wilbur Hall"
    assert card["same_dorm"] is True and card["distance_min"] == 1
    assert card["owner"]["name"] == "Owner" and card["owner"]["dorm_name"] == "Wilbur Hall"
    assert card["thumbnail_url"] is None and card["match_score"] is None
    assert card["created_at"].endswith("Z")


def test_community_counts_are_visibility_aware(db, client, world):
    make_item(db, world["owner"]["id"], "dorm", [world["wilbur"]])
    make_item(db, world["owner"]["id"], "campus", [world["campus"]])
    make_request(db, world["owner"]["id"], "dorm", [world["wilbur"]])

    def counts(who, slug):
        c = client.get(f"/api/communities/{slug}", headers=world["headers"][who]).json()
        return c["item_count"], c["open_request_count"]

    assert counts("mate", "wilbur") == (1, 1)
    assert counts("outsider", "wilbur") == (0, 0)  # not visible → not counted
    assert counts("outsider", "campus") == (1, 0)
