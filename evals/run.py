"""uv run --project backend python -m evals.run {scan|parse|search|match|mutual|handoff|all} [--provider P] [--limit N] [--yes]

parse/search/match/mutual are free and use the seeded dev database (`make seed` first).
mutual needs MUTUAL_MATCHING=rules or ai in backend/.env (docs/plans/mutual-matching.md).
handoff is PAID (8 short HarnessRouter tasks, a few cents in total) and needs --yes; it is not
part of `all`. It needs no database (docs/plans/handoff-coordinator.md).
scan uses AI_PROVIDER (mock by default); a paid provider needs --yes.
Reports are written to evals/reports/YYYY-MM-DD-<suite>.md.
"""

import argparse
import asyncio
import json
import statistics
import time
from datetime import date
from pathlib import Path

import evals  # noqa: F401 — puts backend/ on sys.path
from evals.metrics import mean, mrr, ndcg_at_k, p95, precision_at_k

HERE = Path(__file__).resolve().parent
DATA, REPORTS = HERE / "data", HERE / "reports"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def report(suite: str, lines: list[str]) -> str:
    REPORTS.mkdir(exist_ok=True)
    text = "\n".join([f"# Eval: {suite} — {date.today().isoformat()}", "", *lines, ""])
    (REPORTS / f"{date.today().isoformat()}-{suite}.md").write_text(text)
    print(text)
    return text


# ---------------------------------------------------------------- parse
def run_parse(limit: int | None) -> dict:
    from app.ai.request_parser import parse_request

    rows = load(DATA / "parse" / "requests.jsonl")[:limit]
    fields: dict[str, list[bool]] = {}
    misses = []
    for row in rows:
        p = parse_request(row["text"], date.fromisoformat(row["now"])).model_dump(mode="json")
        for field, gold in row["gold"].items():
            ok = (str(p.get(field)).lower() == str(gold).lower())
            fields.setdefault(field, []).append(ok)
            if not ok:
                misses.append(f"- `{row['text']}` · {field}: got `{p.get(field)}`, want `{gold}`")
    acc = {f: mean(v) for f, v in fields.items()}
    lines = [f"{len(rows)} requests.", "", "| field | accuracy | n |", "|---|---|---|"]
    lines += [f"| {f} | {acc[f]:.2f} | {len(fields[f])} |" for f in sorted(acc)]
    lines += ["", "Targets: kind and category ≥ 0.85, dates ≥ 0.90.", "", "## Misses", *misses[:40]]
    report("parse", lines)
    return acc


# ---------------------------------------------------------------- search
def _viewer(db, seed_key: str):
    from sqlalchemy import select

    from app.models import User
    from app.services.viewer import build_viewer

    user = db.scalar(select(User).where(User.seed_key == seed_key))
    if user is None:
        raise SystemExit(f"{seed_key} not found — run `make seed` first")
    return build_viewer(db, user)


def run_search(limit: int | None) -> dict:
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.discovery import search as S
    from app.models import Item

    from app.discovery.embeddings import warm_up

    warm_up()  # don't count the one-time model load as query latency
    rows = load(DATA / "search" / "queries.jsonl")[:limit]
    out = {"ndcg": [], "p5": [], "mrr": [], "zero": 0, "lat": [], "demo_hits": 0, "demo": 0}
    detail = []
    with SessionLocal() as db:
        keys = dict(db.execute(select(Item.id, Item.seed_key)).all())
        for row in rows:
            viewer = _viewer(db, row["viewer"])
            t = time.perf_counter()
            r = S.search(db, viewer, q=row["q"], kind="items", filters=S.Filters(), offset=0, limit=10)
            out["lat"].append((time.perf_counter() - t) * 1000)
            ranked = [keys.get(i.id) or f"id:{i.id}" for i in r.items]
            rel = {k: v for k, v in row["relevant"].items() if v > 0}
            out["ndcg"].append(ndcg_at_k(ranked, rel))
            out["p5"].append(precision_at_k(ranked, set(rel)))
            out["mrr"].append(mrr(ranked, set(rel)))
            out["zero"] += not ranked
            if row.get("demo"):
                out["demo"] += 1
                out["demo_hits"] += any(k in rel for k in ranked[:3])
            detail.append(f"| {row['q']} | {out['ndcg'][-1]:.2f} | {out['mrr'][-1]:.2f} | "
                          f"{', '.join(i.name[:26] for i in r.items[:3])} |")
    lines = [
        f"{len(rows)} queries on the seed.",
        "",
        f"- **Demo queries with the expected item in the top 3: {out['demo_hits']}/{out['demo']}**",
        f"- nDCG@10 {mean(out['ndcg']):.3f} · P@5 {mean(out['p5']):.3f} · MRR {mean(out['mrr']):.3f}",
        f"- zero-result queries: {out['zero']} · p95 latency {p95(out['lat']):.0f} ms "
        f"(p50 {statistics.median(out['lat']):.0f} ms)",
        "",
        "| query | nDCG@10 | MRR | top 3 |",
        "|---|---|---|---|",
        *detail,
    ]
    report("search", lines)
    return out


# ---------------------------------------------------------------- match
def run_match(limit: int | None) -> dict:
    from sqlalchemy import select

    from app.ai.request_parser import parse_request
    from app.core.db import SessionLocal
    from app.discovery import matching as M
    from app.discovery.embeddings import embed_passages
    from app.discovery.texts import request_text
    from app.models import Item, ItemRequest
    from app.services.visibility import campus_id, item_visible_clause

    rows = load(DATA / "match" / "requests.jsonl")[:limit]
    recalls, precisions, detail = [], [], []
    with SessionLocal() as db:
        keys = dict(db.execute(select(Item.id, Item.seed_key)).all())
        campus = campus_id(db)
        for row in rows:
            viewer = _viewer(db, row["requester"])
            p = parse_request(row["text"])
            req = ItemRequest(requester_id=viewer.user_id, raw_text=row["text"], title=p.title,
                              item_name=p.item_name, category=p.category, attributes=p.attributes,
                              visibility="campus", status="open")
            req.embedding = embed_passages([request_text(req)])[0]
            base = [Item.archived.is_(False), Item.status.in_(M.MATCH_STATUSES),
                    Item.owner_id != viewer.user_id, M._owner_can_view([campus])]
            if row.get("private"):
                conds = [*base, Item.visibility == "private", Item.pings_enabled.is_(True)]
            else:
                conds = [*base, Item.visibility != "private", item_visible_clause(viewer)]
            top = [keys.get(s.item.id) for s in M._diverse(M.score_items(db, viewer, req, conds))[:5]]
            expected = set(row["expected"])
            hit = len(expected & set(top))
            recalls.append(hit / min(5, len(expected)))
            precisions.append(hit / len(top) if top else 0.0)
            detail.append(f"| {row['text'][:50]} | {hit}/{min(5, len(expected))} | {len(top)} |")
            db.expunge_all()
    lines = [
        f"{len(rows)} requests on the seed (public matches, or private pings where marked).",
        "",
        f"- **recall@5 {mean(recalls):.2f}** (target ≥ 0.80) · precision@5 {mean(precisions):.2f}",
        "",
        "| request | expected found in top 5 | returned |",
        "|---|---|---|",
        *detail,
    ]
    report("match", lines)
    return {"recall": mean(recalls), "precision": mean(precisions)}


# ---------------------------------------------------------------- scan
# ---------------------------------------------------------------- mutual matching
def run_mutual(limit: int | None) -> dict:
    """Pairs on the seed: are they the expected ones, are they valid both ways, do they leak?"""
    from sqlalchemy import select

    from app.core.config import settings
    from app.discovery import mutual as MM
    from app.models import Item, User
    from app.services.visibility import item_visible_clause

    if MM.mode() == "off":
        raise SystemExit("MUTUAL_MATCHING is off in backend/.env — set it to rules or ai")
    rows = load(DATA / "mutual" / "pairs.jsonl")[:limit]
    precisions, recalls, times, detail = [], [], [], []
    shown = invalid = leaks = guesses = 0
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        keys = dict(db.execute(select(User.id, User.seed_key)).all())
        opted_in = set(db.scalars(select(User.id).where(User.match_suggestions.is_(True))))
        for row in rows:
            viewer = _viewer(db, row["user"])
            start = time.perf_counter()
            out = MM.mutual_matches(db, viewer)
            times.append((time.perf_counter() - start) * 1000)
            top = out.matches[:3]
            got = [keys.get(m.user.id) for m in top]
            expected = set(row["expected"])
            hit = len(expected & set(got))
            if expected:
                recalls.append(hit / min(3, len(expected)))
            if got:
                precisions.append(hit / len(got))
            for m in out.matches:
                shown += 1
                guesses += m.uses_prediction
                theirs = [link.item.id for link in m.you_get]
                visible = set(
                    db.scalars(
                        select(Item.id).where(
                            Item.id.in_(theirs), Item.visibility != "private",
                            item_visible_clause(viewer),
                        )
                    )
                )
                real = any(link.need.kind == "request" for link in m.you_give + m.you_get)
                ok = bool(m.you_give) and bool(m.you_get) and real and set(theirs) <= visible
                invalid += not ok
                leaks += (m.user.id not in opted_in) or not (set(theirs) <= visible)
            detail.append(f"| {row['user']} | {', '.join(row['expected']) or '—'} | {', '.join(got) or '—'} |")
            db.expunge_all()
    validity = 1 - invalid / shown if shown else 1.0
    lines = [
        f"{len(rows)} people on the seed, MUTUAL_MATCHING={settings.mutual_matching}. "
        f"{shown} pair views shown, {guesses} of them with an AI guess on one side.",
        "",
        f"- **precision@3 {mean(precisions):.2f}** (target ≥ 0.80) · **recall@3 {mean(recalls):.2f}** "
        "(target ≥ 0.80)",
        f"- **validity {validity:.2f}** (target 1.00): both sides have a link, at least one side is a "
        "real request, and every item shown is visible to the viewer",
        f"- **privacy leaks {leaks}** (target 0): pairs with someone who is opted out, or showing an "
        "item the viewer can't open",
        f"- p95 {p95(times):.0f} ms per call (target < 300 ms)",
        "",
        "| person | expected partners | returned (top 3) |",
        "|---|---|---|",
        *detail,
    ]
    report("mutual", lines)
    return {"precision": mean(precisions), "recall": mean(recalls), "validity": validity, "leaks": leaks}


# ---------------------------------------------------------------- handoff coordinator
HANDOFF_NOW = "2026-11-19T10:00:00-08:00"  # a Thursday morning on campus; every chat is read "then"
HANDOFF_PLACES = [
    (1, "Tresidder Memorial Union"), (2, "Cecil H. Green Library"), (3, "Old Union"),
    (4, "Main Quad"), (5, "Arrillaga Family Dining Commons"), (6, "Meyer Green"),
]  # fmt: skip


def _balance(slot) -> float | None:
    """The account's remaining credit: the only real cost figure, since tasks report none."""
    import httpx

    from app.core.config import settings

    try:
        r = httpx.get(
            settings.harnessrouter_base_url.rstrip("/") + "/v1/balance",
            headers={"Authorization": f"Bearer {slot.api_key}"},
            timeout=20,
        )
        return float(r.json()["balance_usd"]) if r.status_code == 200 else None
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None


def score_handoff(row: dict, suggestion, places: dict[int, str]) -> list[str]:
    """What is wrong with one suggestion (an empty list = as expected)."""
    exp, problems = row["expect"], []
    local = suggestion.start_time
    hour = local.hour + local.minute / 60
    if "date" in exp and local.date().isoformat() != exp["date"]:
        problems.append(f"day {local.date().isoformat()} (expected {exp['date']})")
    lo, hi = exp.get("hour", [0, 24])
    if not lo <= hour <= hi:
        problems.append(f"time {local:%H:%M} (expected {lo}–{hi}h)")
    if exp.get("place") and places[suggestion.place_id] != exp["place"]:
        problems.append(f"place {places[suggestion.place_id]} (expected {exp['place']})")
    if "max_confidence" in exp and suggestion.confidence > exp["max_confidence"]:
        problems.append(f"confidence {suggestion.confidence} (expected ≤ {exp['max_confidence']})")
    for banned in exp.get("reason_must_not_contain", []):
        if banned.lower() in suggestion.reason.lower():
            problems.append(f"reason repeats injected text ({banned!r})")
    return problems


def run_handoff(limit: int | None, yes: bool, slot=None, label: str | None = None) -> dict:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.ai import handoff as H
    from app.ai.providers.base import ProviderError
    from app.core.config import settings

    rows = load(DATA / "handoff" / "chats.jsonl")[:limit]
    if slot is None and not H.is_set_up():
        raise SystemExit("Set HARNESSROUTER_HANDOFF_HARNESS_ID first (setup_harnessrouter.py --handoff)")
    if not yes:
        est = len(rows) * settings.handoff_est_cost_per_run
        raise SystemExit(f"{len(rows)} paid tasks, about ${est:.2f} by the estimate. Add --yes to run.")
    slot = slot or H._slot()
    now = datetime.fromisoformat(HANDOFF_NOW).astimezone(ZoneInfo(settings.campus_tz))
    places = dict(HANDOFF_PLACES)
    by_name = {name: pid for pid, name in HANDOFF_PLACES}
    names = {"lender": ["Maya C.", "Maya"], "borrower": ["Jordan R.", "Jordan"]}
    before = _balance(slot)
    valid = correct = 0
    times, detail, reported = [], [], []
    for row in rows:
        payload = H.build_input(
            [tuple(m) for m in row["messages"]], HANDOFF_PLACES,
            lender_dorm="Wilbur Hall", borrower_dorm="Florence Moore Hall (FloMo)",
            pickup_place_id=by_name.get(row.get("pickup_place")), names=names, now=now,
        )  # fmt: skip
        start = time.perf_counter()
        try:
            s = asyncio.run(asyncio.wait_for(H.run_task(payload, now, slot=slot), 120))
        except (ProviderError, TimeoutError, OSError) as exc:
            times.append(time.perf_counter() - start)
            detail.append(f"| {row['name']} | — | — | ✗ no usable answer ({str(exc)[:60]}) |")
            continue
        times.append(time.perf_counter() - start)
        valid += 1
        if s.cost_usd is not None:
            reported.append(s.cost_usd)
        problems = score_handoff(row, s, places)
        correct += not problems
        got = f"{s.start_time:%a %b %d %H:%M} · {places[s.place_id]} · conf {s.confidence}"
        mark = "✓" if not problems else "✗ " + "; ".join(problems)
        detail.append(f"| {row['name']} | {got} | {s.reason[:70]} | {mark} |")
    after = _balance(slot)
    if before is not None and after == before:  # the balance can take a moment to catch up
        time.sleep(45)
        after = _balance(slot)
    spent = round(before - after, 4) if before is not None and after is not None else None
    n = len(rows)
    cost_line = (
        f"- **real cost ${spent:.4f} for {n} tasks (${spent / n:.4f} each)**, read from the account "
        "balance before and after (other use of the same account in that minute would be included)"
        if spent is not None
        else "- real cost: the balance could not be read; check the HarnessRouter dashboard"
    )
    lines = [
        f"{n} sample chats, read as if it were {HANDOFF_NOW}. Harness `{H.HARNESS_NAME}`"
        f"{f' ({label})' if label else ''}, dsh base, no tools.",
        "",
        f"- **valid answers {valid}/{n}** (a place from the list, a time in the future within 7 days)",
        f"- **as expected {correct}/{n}** (the right day, time window and place; injected text ignored)",
        f"- **latency p50 {statistics.median(times):.1f} s** · p95 {p95(times):.1f} s · max {max(times):.1f} s",
        cost_line,
        f"- cost reported by the tasks themselves: {f'${sum(reported):.4f}' if reported else 'none'}",
        "",
        "| chat | suggestion | reason | result |",
        "|---|---|---|---|",
        *detail,
    ]
    if label is None:
        report("handoff", lines)
    else:
        print("\n".join(lines))
    return {"valid": valid, "correct": correct, "n": n, "p50": statistics.median(times), "spent": spent}


def run_scan(limit: int | None, provider_name: str | None, yes: bool) -> dict:
    from app.ai.providers.base import _provider
    from app.ai.vision import downscale
    from app.core.config import settings
    from app.discovery.embeddings import embed_passages

    labels = load(DATA / "scan" / "labels.jsonl")[:limit]
    if not labels:
        print("No labeled photos yet — see evals/data/scan/README.md")
        return {}
    name = provider_name or settings.ai_provider
    if name != "mock":
        est = settings.harnessrouter_est_cost_per_image if name == "harnessrouter" else 0.05
        print(f"PAID run: {len(labels)} photos × ~${est:.2f} ≈ ${len(labels) * est:.2f} on {name}")
        if not yes:
            raise SystemExit("Re-run with --yes to spend it (ask your human first).")
    provider = _provider(name)

    def sim(a: str, b: str) -> float:
        va, vb = embed_passages([a, b])
        return sum(x * y for x, y in zip(va, vb, strict=True))

    tp = fp = fn = leaks = sens_total = cat_ok = qty_ok = 0
    lat, cost = [], []
    for row in labels:
        img = downscale((DATA / "scan" / "images" / row["image"]).read_bytes())
        res = asyncio.run(provider.detect(img, row["image"]))
        lat.append(res.latency_ms / 1000)
        cost.append(res.cost_usd or 0)
        gold = list(row["items"])
        for g in gold:
            sens_total += bool(g.get("sensitive"))
        for d in res.items:
            best = max(
                ((sim(d.name, g["name"]), i) for i, g in enumerate(gold) if g["category"] == d.category),
                default=(0, -1),
            )
            if best[0] >= 0.75:
                g = gold.pop(best[1])
                tp += 1
                cat_ok += 1
                qty_ok += int(g.get("quantity", 1)) == d.quantity
                leaks += bool(g.get("sensitive")) and d.suggested_share
            else:
                fp += 1
        fn += len(gold)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    lines = [
        f"{len(labels)} photos · provider `{name}` / `{provider.model}`.",
        "",
        f"- **found {recall:.0%} of the items** · precision {precision:.2f} · F1 {f1:.2f}",
        f"- quantity exact {qty_ok / tp if tp else 0:.2f} · sensitive leaks {leaks}/{sens_total}",
        f"- p50 {statistics.median(lat):.1f} s · p95 {p95(lat):.1f} s per photo · "
        f"~${mean(cost):.3f} per photo",
        "",
        "Targets: recall ≥ 0.70, precision ≥ 0.80, leak rate 0, p50 ≤ 45 s.",
    ]
    report("scan", lines)
    return {"recall": recall, "precision": precision, "leaks": leaks}


def _mutual_on() -> bool:
    from app.discovery import mutual

    return mutual.mode() != "off"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", choices=["scan", "parse", "search", "match", "mutual", "handoff", "all"])
    ap.add_argument("--provider")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.suite in ("parse", "all"):
        run_parse(a.limit)
    if a.suite in ("search", "all"):
        run_search(a.limit)
    if a.suite in ("match", "all"):
        run_match(a.limit)
    if a.suite == "mutual" or (a.suite == "all" and _mutual_on()):
        run_mutual(a.limit)
    if a.suite == "handoff":
        run_handoff(a.limit, a.yes)
    if a.suite in ("scan", "all"):
        run_scan(a.limit, a.provider, a.yes)


if __name__ == "__main__":
    main()
