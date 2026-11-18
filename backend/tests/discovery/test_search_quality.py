"""Demo-query quality on the real seed with real fastembed. RUN_SLOW=1 uv run pytest -m slow"""

import os

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.discovery import search as S
from app.models import User
from app.seed.seed import run
from app.services.viewer import build_viewer

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="set RUN_SLOW=1"),
]

EXPECTED = [
    ("graphing calculator near me", "graphing calculator"),
    ("anyone have a vacuum in my dorm?", "vacuum"),
    ("formal clothes for an interview", ("suit", "blazer")),
    ("moving boxes available this weekend", "moving boxes"),
    ("someone who can help repair my bike", "bike repair"),
]


def test_demo_queries_top3(db, monkeypatch):
    monkeypatch.setattr(settings, "embeddings_provider", "fastembed")
    run(do_reset=True)
    db.rollback()
    sam = db.scalar(select(User).where(User.email == "sam@demo.daha"))
    viewer = build_viewer(db, sam)
    for q, expected in EXPECTED:
        r = S.search(db, viewer, q=q, kind="items", filters=S.Filters(), offset=0, limit=3)
        top = [i.name.lower() for i in r.items]
        wanted = expected if isinstance(expected, tuple) else (expected,)
        assert any(w in n for n in top for w in wanted), (q, top)
        if "my dorm" in q:
            assert all(i.same_dorm for i in r.items), (q, top)
        if "near me" in q:
            assert r.items[0].same_dorm, (q, top)
    db.rollback()
