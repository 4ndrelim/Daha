from typing import Annotated

from fastapi import Query

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=50)]


def page_of[T](rows: list[T], offset: int, limit: int) -> tuple[list[T], int | None]:
    """Give it up to limit+1 rows; returns (the page, next_offset or None)."""
    has_more = len(rows) > limit
    return rows[:limit], (offset + limit if has_more else None)
