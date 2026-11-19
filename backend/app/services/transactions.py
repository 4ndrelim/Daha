"""Transaction state machine (PLAN.md §7.7): one allowed_actions(), one apply_action().

Every side effect lives here: item and request status, auto-declines, the timeline, system
messages, notifications, points, and badges. Nothing in this module commits; routers do.
"""

from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.geo import campus_today
from app.models import (
    Conversation,
    ConversationParticipant,
    Item,
    ItemRequest,
    Message,
    Place,
    Review,
    Transaction,
    TransactionEvent,
    User,
)
from app.services import condition, handoff, points, serializers
from app.services.notifications import notify
from app.services.viewer import ViewerContext

ACTIVE_STATUSES = ("requested", "offered", "accepted", "handed_off")
PENDING_STATUSES = ("requested", "offered")
PAST_STATUSES = ("completed", "declined", "cancelled")


def _now() -> datetime:
    return datetime.now(UTC)


def _first(user: User) -> str:
    return user.name.split()[0] if user.name.strip() else "Someone"


# ---------------------------------------------------------------- rules
def role_of(tx: Transaction, user_id: int) -> str | None:
    if user_id == tx.owner_id:
        return "owner"
    if user_id == tx.borrower_id:
        return "borrower"
    return None


def allowed_actions(tx: Transaction, user_id: int) -> list[str]:
    """The table in PLAN.md §7.7."""
    role = role_of(tx, user_id)
    if role is None:
        return []
    if tx.status == "requested":
        return ["accept", "decline"] if role == "owner" else ["cancel"]
    if tx.status == "offered":
        return ["cancel"] if role == "owner" else ["accept", "decline"]
    if tx.status == "accepted":
        return ["hand_off", "cancel"]
    if tx.status == "handed_off" and tx.kind == "lend" and role == "owner":
        return ["mark_returned"]
    return []


def is_overdue(tx: Transaction, today: date | None = None) -> bool:
    return (
        tx.status == "handed_off"
        and tx.due_date is not None
        and tx.due_date < (today or campus_today())
    )


# ---------------------------------------------------------------- chat + timeline helpers
def post_message(
    db: Session, conversation_id: int, sender_id: int | None, body: str, *, read_by: int | None
) -> Message:
    """Add a text (sender set) or system (sender None) message. `read_by` has seen it already."""
    msg = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        kind="text" if sender_id is not None else "system",
        body=body,
    )
    db.add(msg)
    db.flush()
    conv = db.get(Conversation, conversation_id)
    conv.last_message_at = _now()
    if read_by is not None:
        participant = db.get(ConversationParticipant, (conversation_id, read_by))
        if participant is not None:
            participant.last_read_message_id = msg.id
    db.flush()
    return msg


def _record(
    db: Session, tx: Transaction, actor: User | None, message: str, note: str | None = None
) -> None:
    """Timeline row + system message for the transaction's new status."""
    db.add(
        TransactionEvent(
            transaction_id=tx.id, status=tx.status, actor_id=actor.id if actor else None, note=note
        )
    )
    post_message(db, tx.conversation_id, None, message, read_by=actor.id if actor else None)


def _other_party(tx: Transaction, user_id: int) -> int:
    return tx.borrower_id if user_id == tx.owner_id else tx.owner_id


def _notify_update(db: Session, tx: Transaction, to_user_id: int, title: str, actor: User | None):
    item = db.get(Item, tx.item_id)
    notify(
        db,
        to_user_id,
        "tx_update",
        title,
        item.name,
        f"/messages/{tx.conversation_id}",
        actor_id=actor.id if actor else None,
        data={"transaction_id": tx.id, "status": tx.status},
    )


# ---------------------------------------------------------------- create
def create_transaction(
    db: Session,
    *,
    item: Item,
    borrower: User,
    initiated_by: str,
    message: str | None = None,
    start_date: date | None = None,
    due_date: date | None = None,
    request: ItemRequest | None = None,
) -> Transaction:
    """A borrow (`initiated_by='borrower'` → requested) or an offer (`'owner'` → offered).

    Creates the transaction together with its conversation; a non-empty message becomes the
    first chat message.
    """
    if start_date and due_date and start_date > due_date:
        raise HTTPException(400, "The return date is before the start date")
    initiator_id = borrower.id if initiated_by == "borrower" else item.owner_id
    conv = Conversation(kind="transaction")
    db.add(conv)
    db.flush()
    message = (message or "").strip() or None
    tx = Transaction(
        kind=item.transaction_type,
        status="requested" if initiated_by == "borrower" else "offered",
        item_id=item.id,
        request_id=request.id if request else None,
        owner_id=item.owner_id,
        borrower_id=borrower.id,
        initiated_by=initiated_by,
        message=message,
        start_date=start_date,
        due_date=due_date,
        pickup_place_id=item.pickup_place_id,
        pickup_note=item.pickup_note,
        conversation_id=conv.id,
    )
    db.add(tx)
    db.flush()
    conv.transaction_id = tx.id
    db.add(ConversationParticipant(conversation_id=conv.id, user_id=item.owner_id))
    db.add(ConversationParticipant(conversation_id=conv.id, user_id=borrower.id))
    db.add(TransactionEvent(transaction_id=tx.id, status=tx.status, actor_id=initiator_id))
    db.flush()
    if message:
        post_message(db, conv.id, initiator_id, message, read_by=initiator_id)
    return tx


# ---------------------------------------------------------------- transitions
def _release(db: Session, tx: Transaction, item: Item, was: str) -> None:
    """Undo what an accepted transaction had claimed (decline/cancel)."""
    if was == "accepted":
        if item.status == "reserved":
            item.status = "available"
        if tx.request_id is not None:
            request = db.get(ItemRequest, tx.request_id)
            still_going = db.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(
                    Transaction.request_id == tx.request_id,
                    Transaction.id != tx.id,
                    Transaction.status.in_(("accepted", "handed_off")),
                )
            )
            if request is not None and request.status == "in_progress" and not still_going:
                request.status = "open"


def _auto_decline(db: Session, tx: Transaction, actor: User, reason: str) -> None:
    tx.status, tx.declined_at = "declined", _now()
    db.add(TransactionEvent(transaction_id=tx.id, status="declined", actor_id=None, note=reason))
    post_message(db, tx.conversation_id, None, reason, read_by=None)
    for user_id in {tx.owner_id, tx.borrower_id} - {actor.id}:
        _notify_update(db, tx, user_id, reason, None)


def _complete(db: Session, tx: Transaction, item: Item, actor: User) -> None:
    """Shared by hand_off (give/exchange) and mark_returned (lend)."""
    tx.status, tx.completed_at = "completed", _now()
    if tx.kind == "lend":
        points.award(
            db, tx.owner_id, points.POINTS_LEND_COMPLETED, "lend_completed", "transaction", tx.id
        )
        points.award(
            db,
            tx.borrower_id,
            points.POINTS_BORROW_COMPLETED,
            "borrow_completed",
            "transaction",
            tx.id,
        )
    elif tx.kind == "give":
        points.award(
            db, tx.owner_id, points.POINTS_GIVE_COMPLETED, "give_completed", "transaction", tx.id
        )
    else:
        for user_id in (tx.owner_id, tx.borrower_id):
            points.award(
                db,
                user_id,
                points.POINTS_EXCHANGE_COMPLETED,
                "exchange_completed",
                "transaction",
                tx.id,
            )

    if tx.request_id is not None:
        request = db.get(ItemRequest, tx.request_id)
        if request is not None and request.status in ("open", "in_progress"):
            request.status, request.fulfilled_at = "fulfilled", _now()
            points.award(
                db,
                tx.owner_id,
                points.POINTS_REQUEST_BONUS,
                "request_fulfilled",
                "transaction",
                tx.id,
            )
            decline_open_offers(
                db,
                request,
                actor,
                "This request was fulfilled by someone else.",
                except_tx_id=tx.id,
            )
    db.flush()
    for user_id in (tx.owner_id, tx.borrower_id):
        points.check_badges(db, user_id)
        notify(
            db,
            user_id,
            "tx_update",
            "All done — leave a review",
            f"How did it go with “{item.name}”?",
            f"/messages/{tx.conversation_id}",
            actor_id=_other_party(tx, user_id),
            data={"transaction_id": tx.id, "status": "completed", "review": True},
        )


def decline_open_offers(
    db: Session,
    request: ItemRequest,
    actor: User,
    reason: str,
    except_tx_id: int | None = None,
) -> None:
    """Auto-decline the request's still-pending offers (it was fulfilled or cancelled)."""
    query = select(Transaction).where(
        Transaction.request_id == request.id, Transaction.status == "offered"
    )
    if except_tx_id is not None:
        query = query.where(Transaction.id != except_tx_id)
    for other in db.execute(query).scalars().all():
        _auto_decline(db, other, actor, reason)


def decline_pending_for_item(
    db: Session, item: Item, actor: User, reason: str, except_tx_id: int | None = None
) -> None:
    """Auto-decline every still-pending borrow request or offer on this item."""
    query = select(Transaction).where(
        Transaction.item_id == item.id, Transaction.status.in_(PENDING_STATUSES)
    )
    if except_tx_id is not None:
        query = query.where(Transaction.id != except_tx_id)
    for other in db.execute(query).scalars().all():
        _auto_decline(db, other, actor, reason)


def apply_action(
    db: Session, tx: Transaction, actor: User, body: schemas.TxActionBody
) -> Transaction:
    """Apply one action from PLAN.md §7.7, or raise 409 if it isn't allowed right now."""
    if body.action not in allowed_actions(tx, actor.id):
        raise HTTPException(409, f"You can't {body.action.replace('_', ' ')} this right now")
    item = db.execute(select(Item).where(Item.id == tx.item_id).with_for_update()).scalar_one()
    who = _first(actor)
    was = tx.status
    other_id = _other_party(tx, actor.id)

    if body.action == "accept":
        if item.status != "available" or item.archived:
            raise HTTPException(409, "This item is no longer available")
        tx.status, tx.accepted_at = "accepted", _now()
        item.status = "reserved"
        if body.pickup_place_id is not None:
            if db.get(Place, body.pickup_place_id) is None:
                raise HTTPException(400, "That pickup spot doesn't exist")
            tx.pickup_place_id = body.pickup_place_id
        if body.due_date is not None:
            tx.due_date = body.due_date
        if tx.request_id is not None:
            request = db.get(ItemRequest, tx.request_id)
            if request is not None and request.status == "open":
                request.status = "in_progress"
        _record(db, tx, actor, f"{who} accepted. Arrange the pickup here.", body.note)
        _notify_update(db, tx, other_id, f"{who} accepted", actor)
        # Everyone else waiting on this same item is told it's taken.
        decline_pending_for_item(
            db, item, actor, f"“{item.name}” went to someone else.", except_tx_id=tx.id
        )

    elif body.action == "decline":
        tx.status, tx.declined_at = "declined", _now()
        _release(db, tx, item, was)
        _record(db, tx, actor, f"{who} declined.", body.note)
        _notify_update(db, tx, other_id, f"{who} declined", actor)

    elif body.action == "cancel":
        tx.status, tx.cancelled_at = "cancelled", _now()
        _release(db, tx, item, was)
        _record(db, tx, actor, f"{who} cancelled.", body.note)
        _notify_update(db, tx, other_id, f"{who} cancelled", actor)

    elif body.action == "hand_off":
        tx.handed_off_at = _now()
        if tx.kind == "lend":
            tx.status = "handed_off"
            item.status = "borrowed"
            _record(db, tx, actor, f"“{item.name}” was handed over.", body.note)
            _notify_update(db, tx, other_id, f"{who} marked it handed over", actor)
        else:
            # A service isn't used up by helping one person; physical items are gone.
            item.status = "available" if item.category == "services" else "unavailable"
            _complete(db, tx, item, actor)
            _record(db, tx, actor, f"“{item.name}” was handed over. All done!", body.note)

    elif body.action == "mark_returned":
        item.status = "available"
        _complete(db, tx, item, actor)
        _record(db, tx, actor, f"{who} got “{item.name}” back. All done!", body.note)

    db.add_all([tx, item])
    db.flush()
    return tx


# ---------------------------------------------------------------- reviews
def create_review(
    db: Session, tx: Transaction, reviewer: User, body: schemas.ReviewCreate
) -> Review:
    if role_of(tx, reviewer.id) is None:
        raise HTTPException(404, "Transaction not found")
    if tx.status != "completed":
        raise HTTPException(409, "You can review once the handoff is complete")
    already = db.scalar(
        select(Review.id).where(Review.transaction_id == tx.id, Review.reviewer_id == reviewer.id)
    )
    if already is not None:
        raise HTTPException(409, "You already reviewed this")
    reviewee_id = _other_party(tx, reviewer.id)
    review = Review(
        transaction_id=tx.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee_id,
        rating=body.rating,
        body=(body.body or "").strip() or None,
    )
    db.add(review)
    db.flush()
    if body.rating >= 4:
        points.award(
            db, reviewee_id, points.POINTS_GOOD_REVIEW, "good_review", "transaction", tx.id
        )
    notify(
        db,
        reviewee_id,
        "review",
        f"{_first(reviewer)} left you a {body.rating}★ review",
        review.body or "",
        "/profile",
        actor_id=reviewer.id,
        data={"transaction_id": tx.id, "rating": body.rating},
    )
    points.check_badges(db, reviewee_id)
    return review


def review_out(db: Session, review: Review) -> schemas.Review:
    return schemas.Review(
        id=review.id,
        transaction_id=review.transaction_id,
        reviewer=serializers.user_refs(db, [review.reviewer_id])[review.reviewer_id],
        reviewee_id=review.reviewee_id,
        rating=review.rating,
        body=review.body,
        created_at=review.created_at,
    )


# ---------------------------------------------------------------- reading
def get_for_party(db: Session, transaction_id: int, user_id: int, *, lock: bool = False):
    """The transaction if the user is one of its two parties, else 404."""
    query = select(Transaction).where(
        Transaction.id == transaction_id,
        or_(Transaction.owner_id == user_id, Transaction.borrower_id == user_id),
    )
    if lock:
        query = query.with_for_update()
    tx = db.execute(query).scalar_one_or_none()
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    return tx


def has_open_transaction(db: Session, item_id: int, user_id: int) -> bool:
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.item_id == item_id,
                Transaction.status.in_(ACTIVE_STATUSES),
                Transaction.borrower_id == user_id,
            )
        )
    )


def transactions_out(
    db: Session, txs: list[Transaction], viewer: ViewerContext
) -> list[schemas.Transaction]:
    """Serialize for one viewer (a party to each), batched."""
    if not txs:
        return []
    ids = [t.id for t in txs]
    items = {
        i.id: i
        for i in db.execute(select(Item).where(Item.id.in_({t.item_id for t in txs}))).scalars()
    }
    cards = {c.id: c for c in serializers.item_cards(db, list(items.values()), viewer)}
    events = (
        db.execute(
            select(TransactionEvent)
            .where(TransactionEvent.transaction_id.in_(ids))
            .order_by(TransactionEvent.created_at, TransactionEvent.id)
        )
        .scalars()
        .all()
    )
    user_ids = {t.owner_id for t in txs} | {t.borrower_id for t in txs}
    user_ids |= {e.actor_id for e in events if e.actor_id is not None}
    refs = serializers.user_refs(db, user_ids)
    places = {
        p.id: p
        for p in db.execute(
            select(Place).where(Place.id.in_({t.pickup_place_id for t in txs if t.pickup_place_id}))
        ).scalars()
    }
    reviewed = set(
        db.scalars(
            select(Review.transaction_id).where(
                Review.transaction_id.in_(ids), Review.reviewer_id == viewer.user_id
            )
        )
    )
    timeline: dict[int, list[schemas.TxTimelineEntry]] = {i: [] for i in ids}
    for e in events:
        timeline[e.transaction_id].append(
            schemas.TxTimelineEntry(
                status=e.status,
                at=e.created_at,
                by=refs.get(e.actor_id) if e.actor_id else None,
                note=e.note,
            )
        )
    today = campus_today()
    out = []
    for t in txs:
        role = role_of(t, viewer.user_id) or "borrower"
        # The pickup note is private until both people have agreed (PLAN.md §7.7).
        note_visible = role == "owner" or t.status in ("accepted", "handed_off", "completed")
        place = places.get(t.pickup_place_id)
        out.append(
            schemas.Transaction(
                id=t.id,
                kind=t.kind,
                status=t.status,
                item=cards[t.item_id],
                request_id=t.request_id,
                owner=refs[t.owner_id],
                borrower=refs[t.borrower_id],
                initiated_by=t.initiated_by,
                my_role=role,
                message=t.message,
                start_date=t.start_date,
                due_date=t.due_date,
                is_overdue=is_overdue(t, today),
                pickup_place=serializers.place_out(place, viewer) if place else None,
                pickup_at=t.pickup_at,
                pickup_note=t.pickup_note if note_visible else None,
                conversation_id=t.conversation_id,
                allowed_actions=allowed_actions(t, viewer.user_id),
                can_review=t.status == "completed" and t.id not in reviewed,
                timeline=timeline[t.id],
                created_at=t.created_at,
                updated_at=t.updated_at,
                condition=condition.condition_out(db, t, viewer.user_id),
                handoff=handoff.handoff_out(db, t, viewer),
            )
        )
    return out


def transaction_out(db: Session, tx: Transaction, viewer: ViewerContext) -> schemas.Transaction:
    return transactions_out(db, [tx], viewer)[0]
