import io

from PIL import Image

from app.core import storage
from tests.core.factories import jpeg_with_exif, seed_base, signup


def test_upload_strips_exif_and_resizes(client, db):
    seed_base(db)
    headers, me = signup(client, "Sam")
    original = jpeg_with_exif()
    src = Image.open(io.BytesIO(original))
    assert src.getexif().get(0x010F) == "DahaCam" and src.getexif().get_ifd(0x8825)

    r = client.post(
        "/api/uploads", files={"file": ("desk.jpg", original, "image/jpeg")}, headers=headers
    )
    assert r.status_code == 201, r.text
    up = r.json()
    assert set(up) == {"id", "url", "width", "height"}
    assert up["url"].startswith("/uploads/") and up["url"].endswith(".jpg")
    # 2400×1200 rotated by EXIF orientation 6 → portrait, long side capped at 1600
    assert (up["width"], up["height"]) == (800, 1600)

    stored = storage.read_upload_bytes(db, up["id"])
    out = Image.open(io.BytesIO(stored))
    assert out.format == "JPEG" and out.size == (800, 1600)
    assert len(out.getexif()) == 0 and not out.getexif().get_ifd(0x8825)
    assert "exif" not in out.info and "icc_profile" not in out.info
    assert b"DahaCam" not in stored and b"Exif" not in stored


def test_upload_accepts_png_and_webp_and_rejects_junk(client, db):
    seed_base(db)
    headers, _ = signup(client, "Sam")
    for fmt in ("PNG", "WEBP"):
        buf = io.BytesIO()
        Image.new("RGBA", (300, 200), (10, 20, 30, 128)).save(buf, format=fmt)
        r = client.post(
            "/api/uploads",
            files={"file": (f"x.{fmt.lower()}", buf.getvalue(), f"image/{fmt.lower()}")},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert (r.json()["width"], r.json()["height"]) == (300, 200)

    r = client.post(
        "/api/uploads", files={"file": ("x.jpg", b"not an image", "image/jpeg")}, headers=headers
    )
    assert r.status_code == 400
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    r = client.post(
        "/api/uploads", files={"file": ("x.gif", gif.getvalue(), "image/gif")}, headers=headers
    )
    assert r.status_code == 400
    assert client.post("/api/uploads", files={"file": ("x.jpg", b"x")}).status_code == 401


def test_avatar_from_upload(client, db):
    seed_base(db)
    headers, _ = signup(client, "Sam")
    other, _ = signup(client, "Other")
    up = client.post(
        "/api/uploads", files={"file": ("a.jpg", jpeg_with_exif((200, 200)))}, headers=headers
    ).json()
    me = client.patch("/api/me", json={"avatar_upload_id": up["id"]}, headers=headers).json()
    assert me["avatar_url"] == up["url"]
    # someone else's upload can't become my avatar
    r = client.patch("/api/me", json={"avatar_upload_id": up["id"]}, headers=other)
    assert r.status_code == 400
