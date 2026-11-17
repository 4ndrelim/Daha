from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["requests"])


@router.post("/requests", response_model=schemas.RequestDetail, status_code=201)
def create_request(body: schemas.RequestCreate):
    not_implemented()


@router.get("/requests/{request_id}", response_model=schemas.RequestDetail)
def get_request(request_id: int):
    not_implemented()


@router.patch("/requests/{request_id}", response_model=schemas.RequestDetail)
def update_request(request_id: int, body: schemas.RequestUpdate):
    not_implemented()


@router.get("/me/requests", response_model=list[schemas.RequestCard])
def my_requests():
    not_implemented()


@router.post("/requests/{request_id}/offers", response_model=schemas.Transaction, status_code=201)
def create_offer(request_id: int, body: schemas.OfferCreate):
    not_implemented()
