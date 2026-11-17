from typing import Literal

from pydantic import Field

from app.schemas.common import ID, CommunityKind, GroupType, Schema


class CommunityRef(Schema):
    id: ID
    slug: str
    name: str
    kind: CommunityKind
    emoji: str | None


class Community(CommunityRef):
    description: str | None
    group_type: GroupType | None
    is_private: bool
    member_count: int
    item_count: int
    open_request_count: int
    is_member: bool
    my_role: Literal["member", "admin"] | None
    join_code: str | None  # only shown to admins, else null
    lat: float | None
    lng: float | None
    distance_min: int | None


class CommunityCreate(Schema):
    name: str = Field(min_length=2, max_length=60)
    description: str | None = None
    group_type: GroupType
    is_private: bool
    emoji: str | None = None


class JoinBody(Schema):
    join_code: str | None = None


class Place(Schema):
    id: ID
    name: str
    lat: float
    lng: float
    description: str | None
    distance_min: int | None


class Upload(Schema):
    id: ID
    url: str
    width: int
    height: int
