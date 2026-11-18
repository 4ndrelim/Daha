import io
import random

from PIL import Image

from tests.core.factories import community_id, seed_base, signup


def photo(seed: int, size=(800, 600)) -> bytes:
    rng = random.Random(seed)
    img = Image.new("RGB", size, tuple(rng.randrange(256) for _ in range(3)))
    for _ in range(20):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        img.paste(tuple(rng.randrange(256) for _ in range(3)), (x, y, x + 60, y + 60))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


def upload(client, headers, seed: int) -> int:
    r = client.post(
        "/api/uploads", headers=headers, files={"file": ("p.jpg", photo(seed), "image/jpeg")}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def user_in_wilbur(client, db, name="Sam"):
    seed_base(db)
    return signup(client, name, dorm_id=community_id(db, "wilbur"))
