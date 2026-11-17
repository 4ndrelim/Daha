from fastapi import APIRouter

from app import schemas
from app.routers._stub import not_implemented

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[schemas.ConversationSummary])
def list_conversations():
    not_implemented()


@router.post("/conversations", response_model=schemas.ConversationSummary)
def direct_conversation(body: schemas.DirectConversationBody):
    not_implemented()


@router.get("/conversations/{conversation_id}", response_model=schemas.ConversationSummary)
def get_conversation(conversation_id: int):
    not_implemented()


@router.get("/conversations/{conversation_id}/messages", response_model=list[schemas.Message])
def list_messages(conversation_id: int, after_id: int | None = None, limit: int = 50):
    not_implemented()


@router.post(
    "/conversations/{conversation_id}/messages", response_model=schemas.Message, status_code=201
)
def send_message(conversation_id: int, body: schemas.SendMessageBody):
    not_implemented()


@router.post("/conversations/{conversation_id}/read", status_code=204)
def mark_conversation_read(conversation_id: int):
    not_implemented()
