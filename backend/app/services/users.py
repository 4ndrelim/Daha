"""Accounts: signup, login, profile updates."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models import Upload, User
from app.services import communities

MIN_PASSWORD_LENGTH = 8


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()


def signup(db: Session, body: schemas.SignupBody) -> User:
    email = body.email.strip().lower()
    local, _, domain = email.rpartition("@")
    if not local or not domain or " " in email:
        raise HTTPException(400, "Enter a valid email address")
    if domain not in settings.allowed_email_domain_list:
        allowed = " or ".join(f"@{d}" for d in settings.allowed_email_domain_list)
        raise HTTPException(400, f"Sign up with your {allowed} email")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if get_by_email(db, email) is not None:
        raise HTTPException(409, "An account with this email already exists")

    referrer = db.get(User, body.ref_user_id) if body.ref_user_id else None
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        referred_by=referrer.id if referrer else None,
    )
    db.add(user)
    db.flush()
    communities.ensure_campus_membership(db, user.id)
    if body.dorm_id is not None:
        communities.set_dorm(db, user.id, body.dorm_id)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return user


def update_me(db: Session, user: User, body: schemas.MeUpdate) -> User:
    sent = body.model_fields_set
    if "name" in sent and body.name is not None:
        user.name = body.name.strip()
    if "bio" in sent:
        user.bio = body.bio
    if "avatar_upload_id" in sent:
        if body.avatar_upload_id is None:
            user.avatar_url = None
        else:
            upload = db.get(Upload, body.avatar_upload_id)
            if upload is None or upload.owner_id != user.id:
                raise HTTPException(400, "Upload the photo first")
            user.avatar_url = upload.url
    if "walking_radius_min" in sent and body.walking_radius_min is not None:
        user.walking_radius_min = body.walking_radius_min
    if "onboarded" in sent and body.onboarded is not None:
        user.onboarded = body.onboarded
    if "dorm_id" in sent and body.dorm_id is not None:
        communities.set_dorm(db, user.id, body.dorm_id)
    db.add(user)
    db.flush()
    return user
