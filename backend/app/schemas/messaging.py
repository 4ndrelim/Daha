from typing import Any, Literal

from pydantic import Field

from app.schemas.common import (
    ID,
    ISODateTime,
    NotificationType,
    Schema,
    TransactionType,
    TxStatus,
)
from app.schemas.users import UserRef


class Message(Schema):
    id: ID
    conversation_id: ID
    sender: UserRef | None
    kind: Literal["text", "system"]
    body: str
    created_at: ISODateTime


class ConversationTransaction(Schema):
    id: ID
    status: TxStatus
    kind: TransactionType
    item_name: str


class ConversationSummary(Schema):
    id: ID
    other_user: UserRef
    transaction: ConversationTransaction | None
    last_message: Message | None
    unread_count: int
    updated_at: ISODateTime


class DirectConversationBody(Schema):
    user_id: ID


class SendMessageBody(Schema):
    body: str = Field(min_length=1, max_length=4000)


class Notification(Schema):
    id: ID
    type: NotificationType
    title: str
    body: str
    link: str
    actor: UserRef | None
    read: bool
    created_at: ISODateTime


class UnreadCounts(Schema):
    notifications: int
    messages: int


class MarkReadBody(Schema):
    ids: list[ID] | None = None
    all: bool | None = None


class EventIn(Schema):
    type: str
    payload: dict[str, Any] | None = None
    ts: ISODateTime | None = None


class EventsBody(Schema):
    events: list[EventIn]
