"""Availability dates on items (docs/plans/availability-dates.md).

An item may carry `available_from` and `available_until` (both optional calendar dates, both
inclusive). Dates are campus dates (CAMPUS_TZ, America/Los_Angeles): "today" is
`geo.campus_today()`, never the server's or the phone's clock.

- now:      no dates, or today is inside them
- upcoming: `available_from` is still ahead ("Available from Fri 21 Nov")
- ended:    `available_until` has passed; the item drops out of search, feeds and matching

This is separate from `items.status` (available / reserved / borrowed / unavailable), which says
whether the thing is free to hand over at all.
"""

from datetime import date
from typing import Literal

from sqlalchemy import and_, func, or_, true

from app.core.geo import campus_today
from app.models import Item, ItemRequest

Window = Literal["now", "upcoming", "ended"]


def nice(d: date) -> str:
    """Fri 21 Nov"""
    return f"{d:%a} {d.day} {d:%b}"


def window(item: Item, today: date | None = None) -> Window:
    today = today or campus_today()
    if item.available_until is not None and item.available_until < today:
        return "ended"
    if item.available_from is not None and item.available_from > today:
        return "upcoming"
    return "now"


def available_now(item: Item, today: date | None = None) -> bool:
    return window(item, today) == "now"


# ---------------------------------------------------------------- SQL
def not_ended_clause(today: date | None = None):
    today = today or campus_today()
    return or_(Item.available_until.is_(None), Item.available_until >= today)


def in_window_clause(today: date | None = None):
    """Inside its dates today."""
    today = today or campus_today()
    return and_(
        or_(Item.available_from.is_(None), Item.available_from <= today),
        not_ended_clause(today),
    )


def overlaps_clause(start: date, end: date):
    """The item's dates share at least one day with start..end."""
    return and_(
        or_(Item.available_from.is_(None), Item.available_from <= end),
        or_(Item.available_until.is_(None), Item.available_until >= start),
    )


def request_days(
    needed_from: date | None, needed_until: date | None, today: date | None = None
) -> tuple[date, date]:
    """The days a request is for. No dates means "now": today only."""
    today = today or campus_today()
    start = max(needed_from or today, today)
    return start, max(needed_until or start, start)


def fits_request(req: ItemRequest, today: date | None = None):
    """For one known request: the item is available on at least one day the request is for."""
    return overlaps_clause(*request_days(req.needed_from, req.needed_until, today))


def fits_joined_request_clause(today: date | None = None):
    """The same rule when ItemRequest is joined in the query (many requests at once)."""
    today = today or campus_today()
    start = func.greatest(func.coalesce(ItemRequest.needed_from, today), today)
    end = func.greatest(func.coalesce(ItemRequest.needed_until, start), start)
    return and_(
        or_(Item.available_from.is_(None), Item.available_from <= end),
        or_(Item.available_until.is_(None), Item.available_until >= start),
    )


def requests_fitting_item_clause(item: Item, today: date | None = None):
    """The mirror image: requests whose days this one item is available on."""
    today = today or campus_today()
    start = func.greatest(func.coalesce(ItemRequest.needed_from, today), today)
    end = func.greatest(func.coalesce(ItemRequest.needed_until, start), start)
    conds = []
    if item.available_from is not None:
        conds.append(end >= item.available_from)
    if item.available_until is not None:
        conds.append(start <= item.available_until)
    return and_(true(), *conds)


# ---------------------------------------------------------------- rules with a message
def dates_problem(
    available_from: date | None, available_until: date | None, today: date | None = None
) -> str | None:
    """What is wrong with a pair of dates someone typed, or None."""
    today = today or campus_today()
    if available_from and available_until and available_from > available_until:
        return "The availability end date is before the start date"
    if available_until and available_until < today:
        return f"The “until” date ({nice(available_until)}) has already passed"
    return None


def borrow_problem(
    item: Item, start_date: date | None, due_date: date | None, today: date | None = None
) -> str | None:
    """Why this borrow request falls outside the item's dates, or None when it fits."""
    today = today or campus_today()
    start = start_date or today
    if item.available_until is not None and item.available_until < today:
        return f"“{item.name}” was only available until {nice(item.available_until)}."
    if item.available_from is not None and start < item.available_from:
        when = nice(item.available_from)
        return f"“{item.name}” is available from {when}. Pick a start date on or after that."
    if item.available_until is not None and start > item.available_until:
        when = nice(item.available_until)
        return f"“{item.name}” is only available until {when}. Pick an earlier start date."
    if item.available_until is not None and due_date and due_date > item.available_until:
        when = nice(item.available_until)
        return f"“{item.name}” needs to be back by {when}. Pick an earlier return date."
    return None
