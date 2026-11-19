"""The mutual-matching opt-in on /me (docs/plans/mutual-matching.md)."""

from app.models import AICache, User
from tests.core.factories import seed_base, signup

KEY = "mutual-profile:{}"


def toggle(client, headers, on: bool) -> None:
    r = client.patch("/api/me", headers=headers, json={"match_suggestions": on})
    assert r.status_code == 200 and r.json()["match_suggestions"] is on, r.text


def test_opting_out_deletes_a_real_users_profile_but_keeps_a_demo_one(client, db):
    seed_base(db)
    real, real_me = signup(client, "Rae")
    demo, demo_me = signup(client, "Demi")
    db.get(User, demo_me["id"]).is_demo = True
    for me in (real_me, demo_me):
        db.add(
            AICache(key=KEY.format(me["id"]), value={"summary": "You lend things.", "needs": []})
        )
    db.commit()

    for headers in (real, demo):
        toggle(client, headers, True)
        toggle(client, headers, False)
    db.expire_all()
    assert db.get(AICache, KEY.format(real_me["id"])) is None  # what was learned is gone
    # The demo profile ships with the seed; keeping it means opting in again costs nothing.
    assert db.get(AICache, KEY.format(demo_me["id"])) is not None
