"""Discovery endpoints (PLAN.md §7.3). Owned by Person C."""

import threading
from typing import Literal

from fastapi import APIRouter, Query

from app import schemas
from app.api.deps import DB, Viewer
from app.discovery import commercial, embeddings, feeds, matching
from app.discovery import search as search_service
from app.services import serializers
from app.services.requests import get_visible_request

router = APIRouter(tags=["discovery"])
# Load the embedding model in the background so the first search isn't slow.
threading.Thread(target=embeddings.warm_up, daemon=True).start()


@router.get("/search", response_model=schemas.SearchResponse)
def search(
    viewer: Viewer,
    db: DB,
    q: str = Query("", max_length=500),
    kind: Literal["all", "items", "requests", "communities"] = "all",
    category: schemas.Category | None = None,
    community_id: int | None = None,
    scope: Literal["campus", "dorm"] | None = None,
    max_walk_min: int | None = Query(None, ge=1, le=120),
    transaction_type: schemas.TransactionType | None = None,
    condition: schemas.Condition | None = None,
    available_only: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
):
    filters = search_service.Filters(
        category=category,
        community_id=community_id,
        scope=scope,
        max_walk_min=max_walk_min,
        transaction_type=transaction_type,
        condition=condition,
        available_only=available_only,
    )
    return search_service.search(
        db, viewer, q=q, kind=kind, filters=filters, offset=offset, limit=limit
    )


@router.post("/search/commercial", response_model=schemas.CommercialSearchResponse)
def commercial_search(body: schemas.CommercialSearchBody, viewer: Viewer, db: DB):
    """Buy or rent nearby (C6): store/rental alternatives for a search, cheapest first.

    POST so an opted-in browser location never ends up in URLs or access logs.
    """
    return commercial.commercial_search(db, viewer, body)


@router.get("/feed/home", response_model=schemas.HomeFeed)
def home_feed(viewer: Viewer, db: DB):
    return feeds.home_feed(db, viewer)


@router.get("/communities/{community_id}/feed", response_model=schemas.Page[schemas.FeedEntry])
def community_feed(
    community_id: int,
    viewer: Viewer,
    db: DB,
    kind: Literal["all", "items", "requests"] = "all",
    offset: int = Query(0, ge=0, le=5000),
    limit: int = Query(20, ge=1, le=50),
):
    return feeds.community_feed(db, viewer, community_id, kind, offset, limit)


@router.get("/requests/{request_id}/matches", response_model=schemas.MatchesResponse)
def request_matches(request_id: int, viewer: Viewer, db: DB):
    req = get_visible_request(db, request_id, viewer)
    rows = matching.visible_matches(db, req, viewer)
    items = [i for i, _ in rows]
    dorms, places = matching.locations(
        db, {i.owner_id for i in items}, {i.pickup_place_id for i in items}
    )
    scores = {
        i.id: (
            s,
            matching.reason(
                viewer,
                matching.loc_for(viewer, i.owner_id, i.pickup_place_id, dorms, places),
                i.status,
            ),
        )
        for i, s in rows
    }
    return schemas.MatchesResponse(
        matching_status=req.matching_status,
        items=serializers.item_cards(db, items, viewer, scores),
        # A number only, never who — and only for the person who asked.
        private_pinged_count=(
            matching.private_pinged_count(db, req.id) if req.requester_id == viewer.user_id else 0
        ),
    )


@router.get("/me/fulfillable", response_model=list[schemas.FulfillableRequest])
def my_fulfillable(viewer: Viewer, db: DB):
    return feeds.fulfillable_out(db, viewer, 20)
