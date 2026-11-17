"""Demo data (PLAN.md §8). Run: `make seed` (= python -m app.seed.seed --reset).

Deterministic: fixed data files and a fixed random seed. `--reset` truncates every table first.
P0-A seeds only the campus, dorms, and exchange points; A2 adds users, items, requests, history.
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Base, Community, Place

DATA_DIR = Path(__file__).parent / "data"


def load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text())


def reset(db: Session) -> None:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def seed_communities(db: Session) -> dict[str, Community]:
    """Campus + dorms, upserted by seed_key. Returns them keyed by slug."""
    rows = [
        {
            "slug": "campus",
            "name": "Stanford Campus",
            "kind": "campus",
            "emoji": "🌲",
            "description": "Everyone at Stanford",
            "lat": None,
            "lng": None,
        }
    ] + [{**d, "kind": "dorm", "description": None} for d in load("dorms.json")]
    out: dict[str, Community] = {}
    for row in rows:
        key = f"community:{row['slug']}"
        c = db.execute(select(Community).where(Community.seed_key == key)).scalar_one_or_none()
        if c is None:
            c = Community(seed_key=key, slug=row["slug"])
            db.add(c)
        c.kind, c.name, c.emoji = row["kind"], row["name"], row["emoji"]
        c.description, c.lat, c.lng = row["description"], row["lat"], row["lng"]
        out[row["slug"]] = c
    db.flush()
    return out


def seed_places(db: Session) -> dict[str, Place]:
    out: dict[str, Place] = {}
    for row in load("places.json"):
        p = db.execute(select(Place).where(Place.name == row["name"])).scalar_one_or_none()
        if p is None:
            p = Place(name=row["name"])
            db.add(p)
        p.lat, p.lng, p.description = row["lat"], row["lng"], row["description"]
        out[row["name"]] = p
    db.flush()
    return out


def run(do_reset: bool = False) -> dict[str, int]:
    from app.discovery import hooks

    with SessionLocal() as db:
        if do_reset:
            reset(db)
        communities = seed_communities(db)
        places = seed_places(db)
        db.commit()
    reindexed = hooks.reindex_all()
    return {"communities": len(communities), "places": len(places), "reindexed": reindexed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DAHA demo data")
    parser.add_argument("--reset", action="store_true", help="truncate every table first")
    args = parser.parse_args()
    counts = run(do_reset=args.reset)
    print("Seeded: " + ", ".join(f"{v} {k}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
