from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["communities"])


@router.get("/communities", response_model=list[schemas.Community])
def list_communities(
    kind: schemas.CommunityKind | None = None, q: str | None = None, mine: bool | None = None
):
    not_implemented()


@router.post("/communities", response_model=schemas.Community, status_code=201)
def create_community(body: schemas.CommunityCreate):
    not_implemented()


@router.get("/communities/{id_or_slug}", response_model=schemas.Community)
def get_community(id_or_slug: str):
    not_implemented()


@router.post("/communities/{community_id}/join", response_model=schemas.Community)
def join_community(community_id: int, body: schemas.JoinBody | None = None):
    not_implemented()


@router.post("/communities/{community_id}/leave", status_code=204)
def leave_community(community_id: int):
    not_implemented()


@router.get("/communities/{community_id}/members", response_model=schemas.Page[schemas.UserRef])
def community_members(community_id: int, offset: int = 0, limit: int = 20):
    not_implemented()


@router.get("/places", response_model=list[schemas.Place])
def list_places():
    not_implemented()
