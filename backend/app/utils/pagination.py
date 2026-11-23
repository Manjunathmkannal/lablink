"""
Pagination helpers.
"""
from math import ceil
from typing import Optional


def offset_paginate(query_cursor, page: int, per_page: int) -> dict:
    """
    Offset-based pagination for equipment / other bounded collections.
    Returns a dict with items, total, page, per_page, pages.
    """
    page = max(1, page)
    per_page = min(max(1, per_page), 100)

    total = query_cursor.count()          # pymongo cursor count
    items = list(query_cursor.skip((page - 1) * per_page).limit(per_page))
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total else 0,
    }


def cursor_paginate(
    collection,
    query: dict,
    sort_field: str,
    sort_dir: int,
    limit: int,
    after_id: Optional[str],
) -> dict:
    """
    Cursor-based pagination for bookings (append-only, fast-growing).
    Uses _id as the opaque cursor.
    Returns items + next_cursor (None when no more pages).
    """
    from bson import ObjectId
    limit = min(max(1, limit), 100)

    if after_id:
        query = dict(query)
        try:
            query["_id"] = {"$gt": ObjectId(after_id)}
        except Exception:
            pass  # ignore bad cursor, start from beginning

    items = list(
        collection.find(query)
        .sort(sort_field, sort_dir)
        .limit(limit + 1)   # fetch one extra to know if there is a next page
    )

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    next_cursor = str(items[-1]["_id"]) if has_more else None
    return {"items": items, "next_cursor": next_cursor}
