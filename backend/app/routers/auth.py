from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app import schemas
from app.api.deps import DB
from app.core.config import settings
from app.core.security import create_token
from app.models import User
from app.services import serializers, users

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(db: DB, user: User) -> schemas.AuthResponse:
    return schemas.AuthResponse(token=create_token(user.id), user=serializers.me_out(db, user))


def _require_demo_mode() -> None:
    if not settings.demo_mode:
        raise HTTPException(404, "Not found")


@router.post("/signup", response_model=schemas.AuthResponse, status_code=201)
def signup(body: schemas.SignupBody, db: DB):
    user = users.signup(db, body)
    db.commit()
    return _auth_response(db, user)


@router.post("/login", response_model=schemas.AuthResponse)
def login(body: schemas.LoginBody, db: DB):
    return _auth_response(db, users.authenticate(db, body.email, body.password))


@router.get("/demo-users", response_model=list[schemas.UserRef])
def demo_users(db: DB):
    _require_demo_mode()
    ids = list(db.scalars(select(User.id).where(User.is_demo.is_(True)).order_by(User.id)))
    refs = serializers.user_refs(db, ids)
    return [refs[i] for i in ids]


@router.post("/demo-login", response_model=schemas.AuthResponse)
def demo_login(body: schemas.DemoLoginBody, db: DB):
    _require_demo_mode()
    user = db.get(User, body.user_id)
    if user is None or not user.is_demo:
        raise HTTPException(404, "Demo user not found")
    return _auth_response(db, user)
