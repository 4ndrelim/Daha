"""Mutual matching: "You two can help each other" (docs/plans/mutual-matching.md). Owned by C.

A mutual match is a pair of people who have BOTH turned matching on, where EACH has an available
item the other needs. Pairs are found here, locally and for free:

- A real need is an open request. C3 already scored it against items and checked visibility both
  ways (the item is visible to the requester, the request is visible to the owner), and stored the
  result in `request_matches`. A strict pair is two of those rows pointing in opposite directions.
- With MUTUAL_MATCHING=ai, one side of a pair may instead be a need the profile agent predicted
  (app/ai/profile.py). Those are guesses: lower weight, labelled, and never the whole pair.

Nothing is stored and nothing is notified in this version: pairs are computed when Home asks.
Other people's private items never count; this module reads `request_matches` and never writes it.
"""

import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.ai import profile as profiles
from app.core.config import settings
from app.discovery.matching import MATCH_STATUSES, score_items
from app.discovery.scoring import loc_for, locations, proximity, reason
from app.models import Item, ItemRequest, RequestMatch, User
from app.services import availability, serializers
from app.services.viewer import ViewerContext, build_viewer
from app.services.visibility import (
    item_visible_clause,
    request_not_expired_clause,
    request_visible_clause,
)

MAX_PAIRS = 10
MAX_LINKS = 3  # per side
REQUEST_WEIGHT = 1.0
PREDICTED_WEIGHT = 0.4  # × the agent's confidence: a guess never outranks a real request
PREDICTION_PARTNERS = 8  # other people's profiles read per call (keeps the endpoint fast)


def mode() -> str:
    return settings.mutual_matching if settings.mutual_matching in ("rules", "ai") else "off"


@dataclass
class Link:
    item: Item
    kind: str  # request | predicted
    name: str
    request: ItemRequest | None
    score: float  # the C3 score of this item for this need
    weight: float

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class _NeedQuery:
    """A predicted need, shaped like the bits of a request that score_items() reads."""

    item_name: str
    embedding: Any
    title: str = ""
    raw_text: str = ""


def _public(*extra) -> list:
    return [
        Item.archived.is_(False),
        Item.status.in_(MATCH_STATUSES),
        Item.visibility != "private",
        availability.in_window_clause(),  # only things that can change hands today
        *extra,
    ]


def _add(links: dict[int, list[Link]], other_id: int, link: Link) -> None:
    rows = links.setdefault(other_id, [])
    if all(existing.item.id != link.item.id for existing in rows):
        rows.append(link)


def _they_asked(db: Session, viewer: ViewerContext) -> dict[int, list[Link]]:
    """Other opted-in people's open requests that my public items answer → {them: links}."""
    rows = db.execute(
        select(RequestMatch.score, ItemRequest, Item)
        .join(ItemRequest, ItemRequest.id == RequestMatch.request_id)
        .join(Item, Item.id == RequestMatch.item_id)
        .join(User, User.id == ItemRequest.requester_id)
        .where(
            RequestMatch.anonymous.is_(False),
            *_public(Item.owner_id == viewer.user_id),
            ItemRequest.requester_id != viewer.user_id,
            ItemRequest.status == "open",
            request_not_expired_clause(),
            request_visible_clause(viewer),
            User.match_suggestions.is_(True),
        )
        .order_by(RequestMatch.score.desc())
    ).all()
    out: dict[int, list[Link]] = {}
    for score, req, item in rows:
        name = (req.item_name or req.title or "").strip()
        _add(out, req.requester_id, Link(item, "request", name, req, float(score), REQUEST_WEIGHT))
    return out


def _i_asked(db: Session, viewer: ViewerContext) -> dict[int, list[Link]]:
    """My open requests that other opted-in people's public items answer → {them: links}."""
    rows = db.execute(
        select(RequestMatch.score, ItemRequest, Item)
        .join(ItemRequest, ItemRequest.id == RequestMatch.request_id)
        .join(Item, Item.id == RequestMatch.item_id)
        .join(User, User.id == Item.owner_id)
        .where(
            RequestMatch.anonymous.is_(False),
            ItemRequest.requester_id == viewer.user_id,
            ItemRequest.status == "open",
            request_not_expired_clause(),
            *_public(Item.owner_id != viewer.user_id, item_visible_clause(viewer)),
            User.match_suggestions.is_(True),
        )
        .order_by(RequestMatch.score.desc())
    ).all()
    out: dict[int, list[Link]] = {}
    for score, req, item in rows:
        name = (req.item_name or req.title or "").strip()
        _add(out, item.owner_id, Link(item, "request", name, req, float(score), REQUEST_WEIGHT))
    return out


def _predicted_links(
    db: Session, needer: ViewerContext, needs: list[dict[str, Any]], conds: list
) -> list[Link]:
    """Items (filtered by `conds`) that answer one person's predicted needs, by the C3 scorer."""
    out: list[Link] = []
    for need in needs:
        name = str(need.get("name") or "")
        if not name:
            continue
        query = _NeedQuery(item_name=name, embedding=need.get("embedding"))
        weight = PREDICTED_WEIGHT * float(need.get("confidence") or 0.5)
        for scored in score_items(db, needer, query, conds, limit=50)[:MAX_LINKS]:  # type: ignore[arg-type]
            out.append(Link(scored.item, "predicted", name, None, scored.score, weight))
    return out


def _add_predictions(
    db: Session,
    viewer: ViewerContext,
    they_asked: dict[int, list[Link]],
    i_asked: dict[int, list[Link]],
) -> tuple[dict[int, list[Link]], dict[int, list[Link]]]:
    """Fill ONE missing side of a pair with a predicted need; the other stays a real request."""
    give = {k: list(v) for k, v in they_asked.items()}
    get = {k: list(v) for k, v in i_asked.items()}
    # They asked for something of mine; might I need something of theirs?
    half = [uid for uid in they_asked if uid not in i_asked]
    mine = profiles.load_profile(db, viewer.user_id)
    if half and mine and mine.get("needs"):
        conds = _public(Item.owner_id.in_(half), item_visible_clause(viewer))
        for link in _predicted_links(db, viewer, mine["needs"], conds):
            _add(get, link.item.owner_id, link)
    # I asked for something of theirs; might they need something of mine?
    for uid in [u for u in i_asked if u not in they_asked][:PREDICTION_PARTNERS]:
        theirs = profiles.load_profile(db, uid)
        other = db.get(User, uid)
        if not theirs or not theirs.get("needs") or other is None:
            continue
        other_viewer = build_viewer(db, other)
        conds = _public(Item.owner_id == viewer.user_id, item_visible_clause(other_viewer))
        for link in _predicted_links(db, other_viewer, theirs["needs"], conds):
            _add(give, uid, link)
    return give, get


def _best(links: list[Link]) -> list[Link]:
    return sorted(links, key=lambda link: (-link.weighted, link.item.id))[:MAX_LINKS]


def _why(place: str, uses_prediction: bool) -> str:
    tail = (
        "one side is a guess"
        if uses_prediction
        else "you both asked"
    )
    return f"{place} · {tail}"


def mutual_matches(db: Session, viewer: ViewerContext) -> schemas.MutualMatchesResponse:
    me = db.get(User, viewer.user_id)
    if me is None or not me.match_suggestions:
        return schemas.MutualMatchesResponse(enabled=False, matches=[])

    give = _they_asked(db, viewer)
    get = _i_asked(db, viewer)
    if mode() == "ai":
        give, get = _add_predictions(db, viewer, give, get)

    partners = [uid for uid in give if uid in get]
    dorms, places = locations(db, set(partners), set())
    pairs = []
    for uid in partners:
        you_give, you_get = _best(give[uid]), _best(get[uid])
        loc = loc_for(viewer, uid, None, dorms, places)
        # geometric mean: one strong side can't carry a weak one
        both = math.sqrt(you_give[0].weighted * you_get[0].weighted)
        score = round(min(both * (0.8 + 0.2 * proximity(viewer, loc)), 1.0), 4)
        guess = any(link.kind != "request" for link in you_give + you_get)
        pairs.append((uid, you_give, you_get, score, guess, reason(viewer, loc)))
    pairs.sort(key=lambda p: (p[4], -p[3], p[0]))  # real pairs first, then by score
    pairs = pairs[:MAX_PAIRS]

    links = [link for _, a, b, *_ in pairs for link in a + b]
    items = {link.item.id: link.item for link in links}
    reqs = {link.request.id: link.request for link in links if link.request is not None}
    item_cards = {c.id: c for c in serializers.item_cards(db, list(items.values()), viewer)}
    req_cards = {c.id: c for c in serializers.request_cards(db, list(reqs.values()), viewer)}
    users = serializers.user_refs(db, [p[0] for p in pairs])

    def out(side: list[Link]) -> list[schemas.MutualLink]:
        return [
            schemas.MutualLink(
                item=item_cards[link.item.id],
                need=schemas.MutualNeed(
                    kind=link.kind,
                    name=link.name,
                    request=req_cards.get(link.request.id) if link.request else None,
                ),
                score=round(link.score, 4),
            )
            for link in side
            if link.item.id in item_cards
        ]

    matches = []
    for uid, you_give, you_get, score, guess, place in pairs:
        gives, gets = out(you_give), out(you_get)
        if uid in users and gives and gets:
            matches.append(
                schemas.MutualMatch(
                    user=users[uid],
                    you_give=gives,
                    you_get=gets,
                    score=score,
                    reason=_why(place, guess),
                    uses_prediction=guess,
                )
            )
    mine = profiles.load_profile(db, viewer.user_id) if mode() == "ai" else None
    return schemas.MutualMatchesResponse(
        enabled=True,
        matches=matches,
        summary=(mine or {}).get("summary"),
        likely_needs=[str(need.get("name")) for need in (mine or {}).get("needs", [])],
    )
