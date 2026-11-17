"""Chat: one thread per transaction, plus one direct thread per pair of users. Polling only."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app import schemas
from app.models import (
    Conversation,
    ConversationParticipant,
    Item,
    Message,
    Transaction,
    User,
)
from app.services import serializers
from app.services.transactions import post_message


def get_for_participant(db: Session, conversation_id: int, user_id: int) -> Conversation:
    """The conversation if the user is in it, else 404."""
    conv = db.execute(
        select(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(Conversation.id == conversation_id, ConversationParticipant.user_id == user_id)
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


def get_or_create_direct(db: Session, user: User, other_id: int) -> Conversation:
    if other_id == user.id:
        raise HTTPException(400, "You can't message yourself")
    if db.get(User, other_id) is None:
        raise HTTPException(404, "User not found")
    mine, theirs = aliased(ConversationParticipant), aliased(ConversationParticipant)
    conv = (
        db.execute(
            select(Conversation)
            .join(mine, mine.conversation_id == Conversation.id)
            .join(theirs, theirs.conversation_id == Conversation.id)
            .where(
                Conversation.kind == "direct", mine.user_id == user.id, theirs.user_id == other_id
            )
            .order_by(Conversation.id)
        )
        .scalars()
        .first()
    )
    if conv is None:
        conv = Conversation(kind="direct")
        db.add(conv)
        db.flush()
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=user.id))
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=other_id))
        db.flush()
    return conv


def list_messages(
    db: Session, conv: Conversation, after_id: int | None, limit: int
) -> list[Message]:
    """Ascending. With after_id: the next messages (polling). Without: the latest `limit`."""
    query = select(Message).where(Message.conversation_id == conv.id)
    if after_id is not None:
        rows = db.execute(
            query.where(Message.id > after_id).order_by(Message.id).limit(limit)
        ).scalars()
        return list(rows)
    rows = db.execute(query.order_by(Message.id.desc()).limit(limit)).scalars()
    return list(reversed(list(rows)))


def send_message(db: Session, conv: Conversation, sender: User, body: str) -> Message:
    text = body.strip()
    if not text:
        raise HTTPException(400, "Write a message first")
    return post_message(db, conv.id, sender.id, text, read_by=sender.id)


def mark_read(db: Session, conv: Conversation, user_id: int) -> None:
    last_id = db.scalar(select(func.max(Message.id)).where(Message.conversation_id == conv.id))
    participant = db.get(ConversationParticipant, (conv.id, user_id))
    if participant is not None and last_id is not None:
        participant.last_read_message_id = last_id
        db.flush()


def messages_out(db: Session, messages: list[Message]) -> list[schemas.Message]:
    refs = serializers.user_refs(db, {m.sender_id for m in messages if m.sender_id is not None})
    return [
        schemas.Message(
            id=m.id,
            conversation_id=m.conversation_id,
            sender=refs.get(m.sender_id) if m.sender_id is not None else None,
            kind=m.kind,
            body=m.body,
            created_at=m.created_at,
        )
        for m in messages
    ]


def summaries(
    db: Session, conversations: list[Conversation], user_id: int
) -> list[schemas.ConversationSummary]:
    """Batched: other participant, transaction chip, last message, unread count."""
    if not conversations:
        return []
    ids = [c.id for c in conversations]

    others = dict(
        db.execute(
            select(ConversationParticipant.conversation_id, ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id.in_(ids),
                ConversationParticipant.user_id != user_id,
            )
        ).all()
    )
    last_ids = (
        select(func.max(Message.id))
        .where(Message.conversation_id.in_(ids))
        .group_by(Message.conversation_id)
    )
    last_messages = {
        m.conversation_id: m
        for m in db.execute(select(Message).where(Message.id.in_(last_ids))).scalars()
    }
    unread = dict(
        db.execute(
            select(Message.conversation_id, func.count())
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == Message.conversation_id,
            )
            .where(
                Message.conversation_id.in_(ids),
                ConversationParticipant.user_id == user_id,
                Message.id > func.coalesce(ConversationParticipant.last_read_message_id, 0),
                Message.sender_id.is_distinct_from(user_id),
            )
            .group_by(Message.conversation_id)
        ).all()
    )
    tx_rows = db.execute(
        select(Transaction, Item.name)
        .join(Item, Item.id == Transaction.item_id)
        .where(Transaction.conversation_id.in_(ids))
    ).all()
    tx_by_conv = {tx.conversation_id: (tx, item_name) for tx, item_name in tx_rows}

    refs = serializers.user_refs(
        db,
        set(others.values())
        | {m.sender_id for m in last_messages.values() if m.sender_id is not None},
    )
    message_out = {
        m.conversation_id: out
        for m, out in zip(
            last_messages.values(), messages_out(db, list(last_messages.values())), strict=True
        )
    }

    out = []
    for c in conversations:
        if c.id not in others or others[c.id] not in refs:
            continue
        tx = tx_by_conv.get(c.id)
        out.append(
            schemas.ConversationSummary(
                id=c.id,
                other_user=refs[others[c.id]],
                transaction=(
                    schemas.ConversationTransaction(
                        id=tx[0].id, status=tx[0].status, kind=tx[0].kind, item_name=tx[1]
                    )
                    if tx
                    else None
                ),
                last_message=message_out.get(c.id),
                unread_count=unread.get(c.id, 0),
                updated_at=c.last_message_at or c.created_at,
            )
        )
    return out


def list_for_user(db: Session, user_id: int) -> list[Conversation]:
    rows = db.execute(
        select(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(ConversationParticipant.user_id == user_id)
        .order_by(func.coalesce(Conversation.last_message_at, Conversation.created_at).desc())
    ).scalars()
    return list(rows)
