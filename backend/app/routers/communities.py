from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import case, select

from app import schemas
from app.api.deps import DB, CurrentUser, Viewer
from app.models import Community, Membership, Place, User
from app.services import communities, serializers
from app.services.pagination import Limit, Offset, page_of
from app.services.viewer import build_viewer

router = APIRouter(tags=["communities"])


@router.get("/communities", response_model=list[schemas.Community])
def list_communities(
    viewer: Viewer,
    db: DB,
    kind: schemas.CommunityKind | None = None,
    q: str | None = None,
    mine: bool | None = None,
):
    query = select(Community)
    if kind:
        query = query.where(Community.kind == kind)
    if q and q.strip():
        query = query.where(Community.name.ilike(f"%{q.strip()}%"))
    if mine:
        query = query.where(Community.id.in_(viewer.community_ids))
    kind_order = case((Community.kind == "campus", 0), (Community.kind == "dorm", 1), else_=2)
    rows = db.execute(query.order_by(kind_order, Community.name)).scalars().all()
    return serializers.communities_out(db, list(rows), viewer)


@router.post("/communities", response_model=schemas.Community, status_code=201)
def create_community(body: schemas.CommunityCreate, user: CurrentUser, db: DB):
    group = communities.create_group(db, user, body)
    db.commit()
    return serializers.community_out(db, group, build_viewer(db, user))


@router.get("/communities/{id_or_slug}", response_model=schemas.Community)
def get_community(id_or_slug: str, viewer: Viewer, db: DB):
    return serializers.community_out(db, communities.get_community(db, id_or_slug), viewer)


@router.post("/communities/{community_id}/join", response_model=schemas.Community)
def join_community(
    community_id: int, user: CurrentUser, db: DB, body: schemas.JoinBody | None = None
):
    community = communities.get_community(db, community_id)
    communities.join(db, user, community, body.join_code if body else None)
    db.commit()
    return serializers.community_out(db, community, build_viewer(db, user))


@router.post("/communities/{community_id}/leave", status_code=204)
def leave_community(community_id: int, user: CurrentUser, db: DB):
    communities.leave(db, user, communities.get_community(db, community_id))
    db.commit()
    return Response(status_code=204)


@router.get("/communities/{community_id}/members", response_model=schemas.Page[schemas.UserRef])
def community_members(
    community_id: int, viewer: Viewer, db: DB, offset: Offset = 0, limit: Limit = 20
):
    community = communities.get_community(db, community_id)
    if community.is_private and community.id not in viewer.community_ids:
        raise HTTPException(404, "Community not found")
    ids = list(
        db.scalars(
            select(User.id)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.community_id == community.id)
            .order_by(User.name, User.id)
            .offset(offset)
            .limit(limit + 1)
        )
    )
    page_ids, next_offset = page_of(ids, offset, limit)
    refs = serializers.user_refs(db, page_ids)
    return schemas.Page[schemas.UserRef](items=[refs[i] for i in page_ids], next_offset=next_offset)


@router.get("/places", response_model=list[schemas.Place])
def list_places(viewer: Viewer, db: DB):
    places = db.execute(select(Place).order_by(Place.id)).scalars().all()
    return [serializers.place_out(p, viewer) for p in places]
