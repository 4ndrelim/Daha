"""Discovery endpoints (PLAN.md §7.3). Owned by Person C."""

import threading
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app import schemas
from app.api.deps import DB, Viewer
from app.discovery import embeddings
from app.discovery import search as search_service

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


@router.get("/feed/home", response_model=schemas.HomeFeed)
def home_feed():
    raise HTTPException(501, "not implemented")


@router.get("/communities/{community_id}/feed", response_model=schemas.Page[schemas.FeedEntry])
def community_feed(
    community_id: int,
    kind: Literal["all", "items", "requests"] = "all",
    offset: int = 0,
    limit: int = 20,
):
    raise HTTPException(501, "not implemented")


@router.get("/requests/{request_id}/matches", response_model=schemas.MatchesResponse)
def request_matches(request_id: int):
    raise HTTPException(501, "not implemented")


@router.get("/me/fulfillable", response_model=list[schemas.FulfillableRequest])
def my_fulfillable():
    raise HTTPException(501, "not implemented")
