"""Discovery endpoints (PLAN.md §7.3). P0-A ships 501 stubs; Person C owns this file from now on."""

from typing import Literal

from fastapi import APIRouter, HTTPException

from app import schemas

router = APIRouter(tags=["discovery"])


@router.get("/search", response_model=schemas.SearchResponse)
def search(
    q: str = "",
    kind: Literal["all", "items", "requests", "communities"] = "all",
    category: schemas.Category | None = None,
    community_id: int | None = None,
    scope: Literal["campus", "dorm"] | None = None,
    max_walk_min: int | None = None,
    transaction_type: schemas.TransactionType | None = None,
    condition: schemas.Condition | None = None,
    available_only: bool = True,
    offset: int = 0,
    limit: int = 20,
):
    raise HTTPException(501, "not implemented")


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
