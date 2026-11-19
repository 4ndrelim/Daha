"""Demo data (PLAN.md §8). Run: `make seed` (= python -m app.seed.seed --reset).

Deterministic: fixed data files and a fixed random seed; dates are relative to the day you seed.
`--reset` truncates every table first. Without it, the campus/dorms/places are upserted and the
demo world is added only if it isn't there yet.

Everything is fictional. Demo accounts use the non-routable domain `demo.daha`.
"""

import argparse
import json
import random
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.geo import campus_today
from app.core.security import hash_password
from app.models import (
    Base,
    Community,
    Conversation,
    ConversationParticipant,
    Item,
    ItemAudience,
    ItemRequest,
    Membership,
    Message,
    Notification,
    Place,
    PointsLedger,
    RequestAudience,
    Review,
    Transaction,
    TransactionEvent,
    User,
)
from app.services import points
from app.services.visibility import resolve_audiences

DATA_DIR = Path(__file__).parent / "data"
DEMO_PASSWORD = "daha-demo"
DEMO_EMAIL_DOMAIN = "demo.daha"
RANDOM_SEED = 42


def load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text())


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:40]


def reset(db: Session) -> None:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


# ---------------------------------------------------------------- base: campus, dorms, places
def seed_communities(db: Session) -> dict[str, Community]:
    """Campus + dorms, upserted by seed_key. Returns them keyed by slug."""
    rows = [
        {
            "slug": "campus",
            "name": "Stanford Campus",
            "kind": "campus",
            "emoji": "🌲",
            "description": "Everyone at Stanford",
            "lat": None,
            "lng": None,
        }
    ] + [{**d, "kind": "dorm", "description": None} for d in load("dorms.json")]
    out: dict[str, Community] = {}
    for row in rows:
        key = f"community:{row['slug']}"
        c = db.execute(select(Community).where(Community.seed_key == key)).scalar_one_or_none()
        if c is None:
            c = Community(seed_key=key, slug=row["slug"])
            db.add(c)
        c.kind, c.name, c.emoji = row["kind"], row["name"], row["emoji"]
        c.description, c.lat, c.lng = row["description"], row["lat"], row["lng"]
        out[row["slug"]] = c
    db.flush()
    return out


def seed_places(db: Session) -> dict[str, Place]:
    out: dict[str, Place] = {}
    for row in load("places.json"):
        p = db.execute(select(Place).where(Place.name == row["name"])).scalar_one_or_none()
        if p is None:
            p = Place(name=row["name"])
            db.add(p)
        p.lat, p.lng, p.description = row["lat"], row["lng"], row["description"]
        out[row["name"]] = p
    db.flush()
    return out


# ---------------------------------------------------------------- the demo world
class DemoSeeder:
    def __init__(self, db: Session, communities: dict[str, Community], places: dict[str, Place]):
        self.db = db
        self.communities = communities
        self.places = list(places.values())
        self.rng = random.Random(RANDOM_SEED)
        self.now = datetime.now(UTC).replace(microsecond=0)
        self.today = campus_today()
        self.users: dict[str, User] = {}
        self.items: dict[str, Item] = {}  # by explicit key, and by "owner:name"
        self.requests: dict[str, ItemRequest] = {}
        self.tx_count = 0

    # ---- date helpers (all relative to the day the seed runs)
    def ago(self, days: float = 0, hours: float = 0) -> datetime:
        return self.now - timedelta(days=days, hours=hours)

    def weekend(self) -> tuple[date, date]:
        """This coming Saturday–Sunday (or what's left of the current weekend)."""
        weekday = self.today.weekday()  # Mon=0 … Sat=5, Sun=6
        if weekday == 6:
            return self.today, self.today
        saturday = self.today + timedelta(days=5 - weekday)
        return saturday, saturday + timedelta(days=1)

    def next_wednesday(self) -> date:
        days = (2 - self.today.weekday()) % 7 or 7
        return self.today + timedelta(days=days)

    def needed(self, spec) -> tuple[date | None, date | None]:
        if spec is None:
            return None, None
        if spec == "weekend":
            return self.weekend()
        if spec == "next_wednesday":
            day = self.next_wednesday()
            return day, day
        start, end = spec
        return self.today + timedelta(days=start), self.today + timedelta(days=end)

    # ---- users, memberships, groups
    def seed_users(self) -> None:
        password_hash = hash_password(DEMO_PASSWORD)  # one hash, reused: keeps the seed fast
        campus = self.communities["campus"]
        for row in load("users.json"):
            user = User(
                email=f"{row['key']}@{DEMO_EMAIL_DOMAIN}",
                password_hash=password_hash,
                name=row["name"],
                bio=row["bio"],
                is_demo=True,
                match_suggestions=True,  # demo accounts show mutual matching; real users opt in
                onboarded=row["key"] != "sam",  # Sam is the onboarding demo account
                seed_key=f"user:{row['key']}",
                created_at=self.ago(days=self.rng.randint(35, 60)),
            )
            self.db.add(user)
            self.db.flush()
            self.users[row["key"]] = user
            self.db.add(Membership(user_id=user.id, community_id=campus.id))
            self.db.add(Membership(user_id=user.id, community_id=self.communities[row["dorm"]].id))
        self.db.flush()

    def seed_groups(self) -> None:
        for row in load("groups.json"):
            group = Community(
                kind="group",
                slug=row["slug"],
                name=row["name"],
                emoji=row["emoji"],
                description=row["description"],
                group_type=row["group_type"],
                is_private=row["is_private"],
                join_code=row.get("join_code"),
                created_by=self.users[row["admin"]].id,
                seed_key=f"community:{row['slug']}",
            )
            self.db.add(group)
            self.db.flush()
            self.communities[row["slug"]] = group
            self.db.add(
                Membership(user_id=self.users[row["admin"]].id, community_id=group.id, role="admin")
            )
            for key in row["members"]:
                self.db.add(Membership(user_id=self.users[key].id, community_id=group.id))
        self.db.flush()

    def _group_ids_of(self, user: User) -> list[int]:
        return list(
            self.db.scalars(
                select(Community.id)
                .join(Membership, Membership.community_id == Community.id)
                .where(Membership.user_id == user.id, Community.kind == "group")
                .order_by(Community.id)
            )
        )

    # ---- items
    def seed_items(self) -> None:
        # Maya's 12 items are explicit; Sam has none (onboarding demo).
        pool = [k for k in self.users if k not in ("maya", "sam")]
        per_day: dict[tuple[int, date], int] = defaultdict(int)
        for index, row in enumerate(load("items.json"), start=1):
            owner_key = row.get("owner") or self.rng.choice(pool)
            owner = self.users[owner_key]
            visibility = (
                row.get("vis")
                or self.rng.choices(["dorm", "campus", "groups"], weights=[85, 10, 5])[0]
            )
            group_ids: list[int] = []
            if visibility == "groups":
                if row.get("group"):
                    group_ids = [self.communities[row["group"]].id]
                else:
                    group_ids = self._group_ids_of(owner)[:1]
                if not group_ids:
                    visibility = "dorm"

            available_from = available_until = None
            if row.get("avail") == "weekend":
                available_from, available_until = self.weekend()

            if row.get("days_ago") is not None:
                # A fixed age draws nothing from the random stream, so adding such a row never
                # reshuffles the rest of the seed.
                place, created_at = None, self.ago(days=row["days_ago"])
            else:
                place = self.rng.choice(self.places) if self.rng.random() < 0.25 else None
                created_at = self.ago(days=self.rng.randint(1, 30), hours=self.rng.randint(0, 23))
            key = row.get("key") or f"{index:03d}-{slugify(row['name'])}"
            item = Item(
                owner_id=owner.id,
                name=row["name"],
                description=row["description"],
                category=row["category"],
                condition=row["condition"],
                transaction_type=row["type"],
                max_lend_days=row.get("max_lend_days"),
                available_from=available_from,
                available_until=available_until,
                visibility=visibility,
                pickup_place_id=place.id if place and visibility != "private" else None,
                pickup_note=(
                    "Text me when you're outside and I'll come down."
                    if visibility != "private" and self.rng.random() < 0.3
                    else None
                ),
                source="manual",
                seed_key=f"item:{key}",
                created_at=created_at,
                updated_at=created_at,
            )
            self.db.add(item)
            self.db.flush()
            for cid in resolve_audiences(self.db, owner, visibility, group_ids):
                self.db.add(ItemAudience(item_id=item.id, community_id=cid))
            self.items[key] = item
            self.items.setdefault(f"{owner_key}:{row['name']}", item)

            # +2 per published (non-private) item, first 10 per owner per day (PLAN.md §7.8)
            if visibility != "private":
                day_key = (owner.id, created_at.date())
                per_day[day_key] += 1
                if per_day[day_key] <= points.ITEM_POINTS_DAILY_CAP:
                    self.ledger(
                        owner, points.POINTS_ITEM_PUBLISHED, "item_published", item, created_at
                    )
        self.db.flush()

    # ---- requests
    def seed_requests(self) -> None:
        for index, row in enumerate(load("requests.json"), start=1):
            requester = self.users[row["requester"]]
            needed_from, needed_until = self.needed(row.get("needed"))
            if row.get("hours_ago") is not None:  # fixed age: see seed_items
                created_at = self.ago(hours=row["hours_ago"])
            else:
                created_at = self.ago(hours=self.rng.randint(1, 60))
            key = row.get("key") or f"{index:02d}-{slugify(row['title'])}"
            req = ItemRequest(
                requester_id=requester.id,
                raw_text=row["raw_text"],
                title=row["title"],
                item_name=row.get("item_name"),
                category=row.get("category"),
                attributes=row.get("attributes", {}),
                quantity=row.get("quantity", 1),
                needed_from=needed_from,
                needed_until=needed_until,
                transaction_type=row.get("type"),
                visibility=row["vis"],
                status="open",
                matching_status="pending",
                seed_key=f"request:{key}",
                created_at=created_at,
                updated_at=created_at,
            )
            self.db.add(req)
            self.db.flush()
            group_ids = [self.communities[row["group"]].id] if row.get("group") else []
            for cid in resolve_audiences(self.db, requester, row["vis"], group_ids):
                self.db.add(RequestAudience(request_id=req.id, community_id=cid))
            self.requests[key] = req
        self.db.flush()

    # ---- low-level writers for history
    def ledger(self, user: User, delta: int, reason: str, ref, at: datetime) -> None:
        self.db.add(
            PointsLedger(
                user_id=user.id,
                delta=delta,
                reason=reason,
                ref_type=ref.__tablename__.rstrip("s"),
                ref_id=ref.id,
                created_at=at,
            )
        )

    def message(self, conv: Conversation, sender: User | None, body: str, at: datetime) -> Message:
        msg = Message(
            conversation_id=conv.id,
            sender_id=sender.id if sender else None,
            kind="text" if sender else "system",
            body=body,
            created_at=at,
        )
        self.db.add(msg)
        self.db.flush()
        conv.last_message_at = at
        return msg

    def event(self, tx: Transaction, status: str, actor: User | None, at: datetime) -> None:
        self.db.add(
            TransactionEvent(
                transaction_id=tx.id,
                status=status,
                actor_id=actor.id if actor else None,
                created_at=at,
            )
        )

    def open_transaction(
        self,
        item: Item,
        borrower: User,
        *,
        initiated_by: str,
        message: str,
        at: datetime,
        request: ItemRequest | None = None,
        start_date: date | None = None,
        due_date: date | None = None,
    ) -> tuple[Transaction, Conversation]:
        owner = self.db.get(User, item.owner_id)
        if item.created_at > at:  # an item can't be borrowed before it was listed
            item.created_at = item.updated_at = at - timedelta(days=2)
        conv = Conversation(kind="transaction", created_at=at)
        self.db.add(conv)
        self.db.flush()
        status = "requested" if initiated_by == "borrower" else "offered"
        tx = Transaction(
            kind=item.transaction_type,
            status=status,
            item_id=item.id,
            request_id=request.id if request else None,
            owner_id=owner.id,
            borrower_id=borrower.id,
            initiated_by=initiated_by,
            message=message,
            start_date=start_date,
            due_date=due_date,
            pickup_place_id=item.pickup_place_id,
            pickup_note=item.pickup_note,
            conversation_id=conv.id,
            created_at=at,
            updated_at=at,
        )
        self.db.add(tx)
        self.db.flush()
        conv.transaction_id = tx.id
        for user in (owner, borrower):
            self.db.add(ConversationParticipant(conversation_id=conv.id, user_id=user.id))
        initiator = borrower if initiated_by == "borrower" else owner
        self.event(tx, status, initiator, at)
        self.message(conv, initiator, message, at)
        self.db.flush()
        self.tx_count += 1
        return tx, conv

    def mark_read(self, conv: Conversation, *users: User) -> None:
        last_id = self.db.scalar(
            select(func.max(Message.id)).where(Message.conversation_id == conv.id)
        )
        for user in users:
            participant = self.db.get(ConversationParticipant, (conv.id, user.id))
            participant.last_read_message_id = last_id

    def completed_deal(
        self,
        item_key: str,
        borrower_key: str,
        days_ago: float,
        ask: str,
        reply: str,
        thanks: str,
        owner_rating: int | None,
        borrower_rating: int | None,
        owner_review: str | None = None,
        borrower_review: str | None = None,
        request: ItemRequest | None = None,
    ) -> None:
        """A finished lend/give/exchange with chat, timeline, reviews, and matching points.

        owner_rating = stars the owner received (from the borrower); borrower_rating likewise.
        """
        item = self.items[item_key]
        owner = self.db.get(User, item.owner_id)
        borrower = self.users[borrower_key]
        kind = item.transaction_type
        first = owner.name.split()[0]
        via_offer = request is not None
        t0 = self.ago(days=days_ago + 3)
        t_accept = t0 + timedelta(hours=2)
        t_handoff = t0 + timedelta(days=1)
        t_done = self.ago(days=days_ago) if kind == "lend" else t_handoff

        tx, conv = self.open_transaction(
            item,
            borrower,
            initiated_by="owner" if via_offer else "borrower",
            message=ask,
            at=t0,
            request=request,
            start_date=t_handoff.date(),
            due_date=t_done.date() if kind == "lend" else None,
        )
        accepter = borrower if via_offer else owner
        tx.status, tx.accepted_at = "accepted", t_accept
        self.event(tx, "accepted", accepter, t_accept)
        self.message(
            conv, None, f"{accepter.name.split()[0]} accepted. Arrange the pickup here.", t_accept
        )
        self.message(
            conv, owner if not via_offer else borrower, reply, t_accept + timedelta(minutes=7)
        )

        tx.handed_off_at = t_handoff
        if kind == "lend":
            self.event(tx, "handed_off", owner, t_handoff)
            self.message(conv, None, f"{first} handed over “{item.name}”.", t_handoff)
            self.message(conv, borrower, thanks, t_done - timedelta(hours=1))
            self.message(conv, None, f"{first} got “{item.name}” back. All done!", t_done)
        else:
            self.message(conv, borrower, thanks, t_handoff - timedelta(minutes=20))
            self.message(conv, None, f"{first} handed over “{item.name}”. All done!", t_handoff)
            item.status = "unavailable" if item.category != "services" else "available"
        tx.status, tx.completed_at, tx.updated_at = "completed", t_done, t_done
        self.event(tx, "completed", owner, t_done)
        self.mark_read(conv, owner, borrower)

        # points (PLAN.md §7.8)
        if kind == "lend":
            self.ledger(owner, points.POINTS_LEND_COMPLETED, "lend_completed", tx, t_done)
            self.ledger(borrower, points.POINTS_BORROW_COMPLETED, "borrow_completed", tx, t_done)
        elif kind == "give":
            self.ledger(owner, points.POINTS_GIVE_COMPLETED, "give_completed", tx, t_done)
        else:
            self.ledger(owner, points.POINTS_EXCHANGE_COMPLETED, "exchange_completed", tx, t_done)
            self.ledger(
                borrower, points.POINTS_EXCHANGE_COMPLETED, "exchange_completed", tx, t_done
            )
        if request is not None:
            request.status, request.fulfilled_at = "fulfilled", t_done
            request.matching_status = "done"
            self.ledger(owner, points.POINTS_REQUEST_BONUS, "request_fulfilled", tx, t_done)

        for reviewer, reviewee, rating, body in (
            (borrower, owner, owner_rating, owner_review),
            (owner, borrower, borrower_rating, borrower_review),
        ):
            if rating is None:
                continue
            at = t_done + timedelta(hours=3)
            self.db.add(
                Review(
                    transaction_id=tx.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    rating=rating,
                    body=body,
                    created_at=at,
                )
            )
            if rating >= 4:
                self.ledger(reviewee, points.POINTS_GOOD_REVIEW, "good_review", tx, at)
        self.db.flush()

    # ---- history: ~10 finished deals + 3 live ones for the hero accounts
    def seed_history(self) -> None:
        u = self.users

        # A fulfilled request, so Maya's binder loan shows the request → offer → lend path.
        t_req = self.ago(days=10)
        portfolio = ItemRequest(
            requester_id=u["nina"].id,
            raw_text="does anyone have a black binder? need one for my portfolio review",
            title="Black binder for portfolio review",
            item_name="black binder",
            category="academic",
            attributes={"color": "black"},
            transaction_type="lend",
            visibility="campus",
            status="open",
            matching_status="done",
            seed_key="request:nina-portfolio-binder",
            created_at=t_req,
            updated_at=t_req,
        )
        self.db.add(portfolio)
        self.db.flush()
        self.db.add(
            RequestAudience(request_id=portfolio.id, community_id=self.communities["campus"].id)
        )

        deal = self.completed_deal
        deal(
            "maya-ti84",
            "alex",
            20,
            "Hey Maya! Could I borrow your TI-84 for my Math 51 midterm on Thursday?",
            "Of course — I'm in the Wilbur lounge after 6 tonight.",
            "Midterm done. Dropping it back at the lounge at 5!",
            5,
            5,
            "Super easy handoff, calculator worked perfectly.",
            "Returned on time.",
        )
        deal(
            "maya-vacuum",
            "priya",
            16,
            "Hi! Could I use your vacuum for an hour this afternoon? Parents are visiting.",
            "Ha, good luck. Knock on my door anytime after 2.",
            "All clean, bin emptied. Thank you!!",
            5,
            5,
            "Lifesaver before parents' weekend.",
            "Emptied the bin and everything.",
        )
        deal(
            "maya-tent",
            "emma",
            12,
            "Could I borrow your tent for a Big Basin trip this weekend?",
            "Yes! Stakes are in the bag. Tresidder at noon Friday?",
            "Back from the trip — tent is dry and packed. Thanks so much.",
            5,
            4,
            "Tent was in great shape. Maya is the best.",
            "Brought it back clean.",
        )
        deal(
            "maya:Electric kettle",
            "alex",
            9,
            "My kettle died mid-finals. Could I borrow yours for a couple of days?",
            "Sure, come grab it.",
            "Bought a new one — yours is back on your desk.",
            4,
            5,
            "Quick and friendly.",
            None,
        )
        deal(
            "maya-black-binder",
            "nina",
            6,
            'I have a black 1.5" binder you can borrow — want it?',
            "Yes please, that would be perfect!",
            "Portfolio review went well. Leaving the binder at Old Union for you.",
            5,
            5,
            "Offered within minutes of my post. Thank you!",
            "Easy and on time.",
            request=portfolio,
        )
        deal(
            "noor:Microwave",
            "ravi",
            8,
            "Is the microwave still available? Our lab kitchen needs one.",
            "It's yours! Come by Mirrielees whenever.",
            "On my way with a cart.",
            5,
            None,
            "Free microwave, works great.",
        )
        deal(
            "omar-navy-suit",
            "mateo",
            10,
            "Could I borrow the navy suit for a career fair on Wednesday?",
            "Sure — it's a 40R. Try it on at Stern tonight?",
            "Got two interviews out of it. Dry-cleaned and ready to return.",
            5,
            5,
            "The suit fit and Omar gave interview tips too.",
            "Dry-cleaned it. Class act.",
        )
        deal(
            "owen:Headshot photography",
            "lila",
            5,
            "Trade you headshots for hemming two pairs of pants?",
            "Deal. Saturday morning light is best — Main Quad at 9?",
            "Photos look amazing. Pants will be ready Monday.",
            5,
            5,
            "Great photos, fair swap.",
            "Perfect hems.",
        )
        deal(
            "mateo:Instant ramen (12 pack)",
            "ben",
            3,
            "Is the ramen still up for grabs?",
            "All yours. Manzanita lobby?",
            "Be there in 10.",
            4,
            None,
            "Free ramen. Enough said.",
        )
        deal(
            "alex:Mirrorless camera (Sony a6000)",
            "owen",
            4,
            "Could I borrow the a6000 as a second body for a shoot on Saturday?",
            "Yep. Battery is charged, SD card is empty.",
            "Shoot went great. Camera is back in its bag, battery recharged.",
            5,
            5,
            "Trusting someone with a camera is big. Thanks Alex.",
            "Careful and punctual.",
        )

        # 1) Someone is waiting on Maya: a borrow request for her chem model kit.
        t = self.ago(hours=3)
        tx, _ = self.open_transaction(
            self.items["maya:Organic chemistry model kit"],
            u["ethan"],
            initiated_by="borrower",
            message="Hi Maya! Could I borrow the model kit for my orgo midterm next week?",
            at=t,
            start_date=self.today + timedelta(days=5),
            due_date=self.today + timedelta(days=8),
        )
        self.notification(
            u["maya"],
            "borrow_request",
            "Ethan wants to borrow your item",
            "Organic chemistry model kit",
            f"/messages/{tx.conversation_id}",
            u["ethan"],
            t,
        )

        # 2) Jordan is currently borrowing Alex's tripod (due in two days).
        t = self.ago(days=3)
        tripod = self.items["alex-tripod"]
        tx, conv = self.open_transaction(
            tripod,
            u["jordan"],
            initiated_by="borrower",
            message="Could I borrow your tripod for a class film project this week?",
            at=t,
            start_date=self.today - timedelta(days=2),
            due_date=self.today + timedelta(days=2),
        )
        tx.status, tx.accepted_at = "accepted", t + timedelta(hours=1)
        self.event(tx, "accepted", u["alex"], tx.accepted_at)
        self.message(conv, None, "Alex accepted. Arrange the pickup here.", tx.accepted_at)
        self.message(
            conv,
            u["alex"],
            "Sure! I can meet at Arrillaga dining at 6.",
            tx.accepted_at + timedelta(minutes=5),
        )
        tx.status, tx.handed_off_at = "handed_off", self.ago(days=2)
        tx.updated_at = tx.handed_off_at
        self.event(tx, "handed_off", u["alex"], tx.handed_off_at)
        self.message(conv, None, f"Alex handed over “{tripod.name}”.", tx.handed_off_at)
        self.mark_read(conv, u["alex"], u["jordan"])
        tripod.status = "borrowed"

        # 3) Maya offered her tent on Jordan's weekend request; Jordan hasn't answered yet.
        t = self.ago(hours=1)
        tent_request = self.requests["jordan-tent"]
        weekend_start, weekend_end = self.weekend()
        tx, _ = self.open_transaction(
            self.items["maya-tent"],
            u["jordan"],
            initiated_by="owner",
            message="I have a 2-person tent you can take to Big Basin!",
            at=t,
            request=tent_request,
            start_date=weekend_start,
            due_date=weekend_end,
        )
        self.notification(
            u["jordan"],
            "offer",
            "Maya offered an item for your request",
            "2-person backpacking tent",
            f"/requests/{tent_request.id}",
            u["maya"],
            t,
        )

        self.notification(
            u["sam"],
            "system",
            "Welcome to DAHA 👋",
            "Snap a photo of your desk to share your first items.",
            "/onboarding",
            None,
            self.ago(hours=2),
        )
        self.db.flush()

    def notification(self, user, type_, title, body, link, actor, at) -> None:
        self.db.add(
            Notification(
                user_id=user.id,
                type=type_,
                title=title,
                body=body,
                link=link,
                actor_id=actor.id if actor else None,
                created_at=at,
            )
        )

    def seed_badges(self) -> None:
        """Badges are derived from the history above, so they always match it."""
        for user in self.users.values():
            points.check_badges(self.db, user.id, send_notifications=False)

    def run(self) -> None:
        self.seed_users()
        self.seed_groups()
        self.seed_items()
        self.seed_requests()
        self.seed_history()
        self.seed_badges()
        self.db.flush()


def _refresh_discovery() -> int:
    """Let C's code index the seeded rows: embeddings first, then matching for open requests."""
    from app.discovery import hooks

    reindexed = hooks.reindex_all()
    with SessionLocal() as db:
        pending = list(
            db.scalars(
                select(ItemRequest.id)
                .where(ItemRequest.status == "open", ItemRequest.matching_status == "pending")
                .order_by(ItemRequest.id)
            )
        )
    for request_id in pending:
        try:
            hooks.on_request_created(request_id)
        except Exception as exc:  # noqa: BLE001 — a matching bug must not break the seed
            print(f"  ! matching failed for request {request_id}: {exc}")
    return reindexed


def run(do_reset: bool = False, demo: bool = True) -> dict[str, int]:
    """`demo=False` seeds only the campus, dorms, and exchange points (a real deployment)."""
    with SessionLocal() as db:
        if do_reset:
            reset(db)
        communities = seed_communities(db)
        places = seed_places(db)
        already = db.scalar(select(User.id).where(User.seed_key == "user:maya"))
        if demo and already is None:
            DemoSeeder(db, communities, places).run()
        db.commit()

        def count(model) -> int:
            return db.scalar(select(func.count()).select_from(model)) or 0

        counts = {
            "communities": count(Community),
            "places": count(Place),
            "users": count(User),
            "items": count(Item),
            "requests": count(ItemRequest),
            "transactions": count(Transaction),
            "reviews": count(Review),
        }
    counts["reindexed"] = _refresh_discovery()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DAHA demo data")
    parser.add_argument("--reset", action="store_true", help="truncate every table first")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="do nothing unless the database has no communities yet (used when a container starts)",
    )
    parser.add_argument(
        "--base-only", action="store_true", help="only campus, dorms, and places — no demo world"
    )
    args = parser.parse_args()
    if args.if_empty:
        with SessionLocal() as db:
            if db.scalar(select(func.count()).select_from(Community)):
                print("Database already has data — not seeding.")
                return
    demo = settings.demo_mode and not args.base_only
    counts = run(do_reset=args.reset and not args.if_empty, demo=demo)
    print("Seeded: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    if demo:
        print(
            f"Demo logins: maya@{DEMO_EMAIL_DOMAIN}, jordan@{DEMO_EMAIL_DOMAIN}, "
            f"sam@{DEMO_EMAIL_DOMAIN} / {DEMO_PASSWORD}"
        )


if __name__ == "__main__":
    main()
