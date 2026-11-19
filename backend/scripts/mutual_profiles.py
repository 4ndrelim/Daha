"""Build habit profiles for mutual matching ahead of time (docs/plans/mutual-matching.md, H4).

    cd backend
    uv run python scripts/mutual_profiles.py --show maya@demo.daha   # free: what we would send
    uv run python scripts/mutual_profiles.py --limit 3 --yes         # PAID: 3 profiles
    uv run python scripts/mutual_profiles.py --yes                   # PAID: everyone who is due
    uv run python scripts/mutual_profiles.py --export-demo           # free: save the demo users'
        # profiles to app/seed/data/mutual_profiles.json, so a reseed brings them back for free

Only people who turned matching on and have at least 3 signals get a profile. Every run costs
about MUTUAL_EST_COST_PER_PROFILE and stops at MUTUAL_BUDGET_USD. Needs MUTUAL_MATCHING=ai and
HARNESSROUTER_PROFILE_HARNESS_ID (scripts/setup_harnessrouter.py --profile --write-env).
Never prints a key, a name or an email.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # `python scripts/x.py` finds `app`

from app.ai import profile  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models import Event, User  # noqa: E402

SEED_FILE = Path(__file__).resolve().parents[1] / "app" / "seed" / "data" / "mutual_profiles.json"


def export_demo() -> None:
    """Demo users are fictional, so their profiles can live in the repo next to the seed data."""
    out = {}
    with SessionLocal() as db:
        for user in db.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.id)):
            row = profile.load_profile(db, user.id)
            if row is None or not user.seed_key:
                continue
            out[user.seed_key] = {
                "summary": row.get("summary"),
                "lends": row.get("lends", []),
                "borrows": row.get("borrows", []),
                "needs": [
                    {k: need.get(k) for k in ("name", "category", "confidence")}
                    for need in row.get("needs", [])
                ],
            }
    SEED_FILE.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"saved {len(out)} demo profile(s) to {SEED_FILE.relative_to(SEED_FILE.parents[3])}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--show", metavar="EMAIL", help="print what would be sent for one person (free)"
    )
    ap.add_argument("--limit", type=int, default=0, help="at most this many paid tasks")
    ap.add_argument("--force", action="store_true", help="refresh even if nothing changed")
    ap.add_argument("--yes", action="store_true", help="really spend money")
    ap.add_argument("--export-demo", action="store_true", help="save demo profiles for the seed")
    args = ap.parse_args()
    if args.export_demo:
        export_demo()
        return

    with SessionLocal() as db:
        if args.show:
            user = db.scalar(select(User).where(User.email == args.show.lower()))
            if user is None:
                sys.exit("no such user")
            payload, signals = profile.build_input(db, user.id)
            print(f"signals: {signals}\n{profile.task_text(payload)}")
            return
        due = []
        for user in db.scalars(
            select(User).where(User.match_suggestions.is_(True)).order_by(User.id)
        ):
            payload, signals = profile.build_input(db, user.id)
            row = profile.load_profile(db, user.id)
            unchanged = row is not None and row.get("input_hash") == profile.input_hash(payload)
            if signals >= profile.MIN_SIGNALS and (args.force or not unchanged):
                due.append(user.id)
        spent = profile.spent(db)
    if args.limit:
        due = due[: args.limit]
    est = len(due) * settings.mutual_est_cost_per_profile
    print(
        f"{len(due)} profile(s) due · estimated ${est:.2f} · spent so far ${spent:.2f} "
        f"of ${settings.mutual_budget_usd:.2f}"
    )
    if settings.mutual_matching != "ai":
        sys.exit("MUTUAL_MATCHING is not 'ai' in backend/.env: nothing was run")
    if not args.yes:
        sys.exit("Add --yes to run them (this spends HarnessRouter credit)")
    for n, user_id in enumerate(due, 1):
        status = profile.refresh_profile(user_id, force=args.force)
        with SessionLocal() as db:
            last = db.scalar(
                select(Event).where(Event.type == profile.EVENT_TYPE).order_by(Event.id.desc())
            )
            row = profile.load_profile(db, user_id)
        info = (
            json.dumps(last.payload) if last is not None and status in ("updated", "failed") else ""
        )
        needs = [need["name"] for need in (row or {}).get("needs", [])]
        print(f"{n}/{len(due)} user #{user_id}: {status} {info} needs={needs}")
        if status == "budget reached":
            break
    with SessionLocal() as db:
        print(f"spent so far: ${profile.spent(db):.2f} of ${settings.mutual_budget_usd:.2f}")


if __name__ == "__main__":
    main()
