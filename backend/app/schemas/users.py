from pydantic import Field

from app.schemas.common import ID, ISODateTime, Schema
from app.schemas.communities import CommunityRef


class UserRef(Schema):
    id: ID
    name: str
    avatar_url: str | None
    dorm_name: str | None
    level_name: str
    rating_avg: float | None


class Badge(Schema):
    code: str
    name: str
    emoji: str
    description: str
    earned_at: ISODateTime


class Level(Schema):
    name: str
    min_points: int
    next_level_name: str | None
    next_level_points: int | None


class UserPublic(UserRef):
    bio: str | None
    points: int
    level: Level
    badges: list[Badge]
    rating_count: int
    completed_count: int
    items_shared_count: int
    joined_at: ISODateTime


class Me(UserPublic):
    email: str
    dorm: CommunityRef | None
    groups: list[CommunityRef]
    walking_radius_min: int
    onboarded: bool
    unread_notifications: int
    unread_messages: int


class AuthResponse(Schema):
    token: str
    user: Me


class SignupBody(Schema):
    email: str
    password: str
    name: str = Field(min_length=1, max_length=80)
    dorm_id: ID | None = None
    ref_user_id: ID | None = None


class LoginBody(Schema):
    email: str
    password: str


class DemoLoginBody(Schema):
    user_id: ID


class MeUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = None
    avatar_upload_id: ID | None = None
    dorm_id: ID | None = None
    walking_radius_min: int | None = Field(default=None, ge=1, le=120)
    onboarded: bool | None = None
