"""Small helpers shared by A's tests. Everything goes through the real API where it exists."""

import io
import itertools

from PIL import Image
from sqlalchemy import select

from app.models import Community, Item, ItemAudience, ItemRequest, RequestAudience
from app.seed.seed import seed_communities, seed_places

_counter = itertools.count(1)


def seed_base(db) -> dict[str, Community]:
    """Campus + dorms + places. Returns communities keyed by slug."""
    communities = seed_communities(db)
    seed_places(db)
    db.commit()
    return communities


def signup(client, name: str = "Test", dorm_id: int | None = None, email: str | None = None):
    """Returns (headers, me)."""
    email = email or f"user{next(_counter)}@stanford.edu"
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password123", "name": name, "dorm_id": dorm_id},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def community_id(db, slug: str) -> int:
    return db.scalar(select(Community.id).where(Community.slug == slug))


def make_item(db, owner_id: int, visibility: str, audience_ids: list[int], **kw) -> Item:
    item = Item(
        owner_id=owner_id,
        name=kw.pop("name", "Graphing calculator"),
        category=kw.pop("category", "academic"),
        transaction_type=kw.pop("transaction_type", "lend"),
        visibility=visibility,
        **kw,
    )
    db.add(item)
    db.flush()
    for cid in audience_ids:
        db.add(ItemAudience(item_id=item.id, community_id=cid))
    db.commit()
    return item


def make_request(db, requester_id: int, visibility: str, audience_ids: list[int], **kw):
    req = ItemRequest(
        requester_id=requester_id,
        raw_text=kw.pop("raw_text", "anyone have a vacuum?"),
        title=kw.pop("title", "Vacuum"),
        visibility=visibility,
        **kw,
    )
    db.add(req)
    db.flush()
    for cid in audience_ids:
        db.add(RequestAudience(request_id=req.id, community_id=cid))
    db.commit()
    return req


def jpeg_with_exif(size=(2400, 1200)) -> bytes:
    """A JPEG carrying EXIF (camera make, GPS block, rotation) like a phone photo."""
    img = Image.new("RGB", size, (200, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "DahaCam"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90° CW
    exif[0x8825] = {1: "N", 2: (37.0, 25.0, 30.0), 3: "W", 4: (122.0, 10.0, 12.0)}  # GPS IFD
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()
