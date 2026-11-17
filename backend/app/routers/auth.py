from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.AuthResponse, status_code=201)
def signup(body: schemas.SignupBody):
    not_implemented()


@router.post("/login", response_model=schemas.AuthResponse)
def login(body: schemas.LoginBody):
    not_implemented()


@router.get("/demo-users", response_model=list[schemas.UserRef])
def demo_users():
    not_implemented()


@router.post("/demo-login", response_model=schemas.AuthResponse)
def demo_login(body: schemas.DemoLoginBody):
    not_implemented()
