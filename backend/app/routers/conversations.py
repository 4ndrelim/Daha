from typing import Annotated

from fastapi import APIRouter, Query, Response

from app import schemas
from app.api.deps import DB, CurrentUser
from app.services import conversations

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[schemas.ConversationSummary])
def list_conversations(user: CurrentUser, db: DB):
    return conversations.summaries(db, conversations.list_for_user(db, user.id), user.id)


@router.post("/conversations", response_model=schemas.ConversationSummary)
def direct_conversation(body: schemas.DirectConversationBody, user: CurrentUser, db: DB):
    """Get or create the direct thread with another user."""
    conv = conversations.get_or_create_direct(db, user, body.user_id)
    db.commit()
    return conversations.summaries(db, [conv], user.id)[0]


@router.get("/conversations/{conversation_id}", response_model=schemas.ConversationSummary)
def get_conversation(conversation_id: int, user: CurrentUser, db: DB):
    conv = conversations.get_for_participant(db, conversation_id, user.id)
    return conversations.summaries(db, [conv], user.id)[0]


@router.get("/conversations/{conversation_id}/messages", response_model=list[schemas.Message])
def list_messages(
    conversation_id: int,
    user: CurrentUser,
    db: DB,
    after_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    conv = conversations.get_for_participant(db, conversation_id, user.id)
    return conversations.messages_out(db, conversations.list_messages(db, conv, after_id, limit))


@router.post(
    "/conversations/{conversation_id}/messages", response_model=schemas.Message, status_code=201
)
def send_message(conversation_id: int, body: schemas.SendMessageBody, user: CurrentUser, db: DB):
    conv = conversations.get_for_participant(db, conversation_id, user.id)
    message = conversations.send_message(db, conv, user, body.body)
    db.commit()
    return conversations.messages_out(db, [message])[0]


@router.post("/conversations/{conversation_id}/read", status_code=204)
def mark_conversation_read(conversation_id: int, user: CurrentUser, db: DB):
    conv = conversations.get_for_participant(db, conversation_id, user.id)
    conversations.mark_read(db, conv, user.id)
    db.commit()
    return Response(status_code=204)
