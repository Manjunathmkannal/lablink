"""
Booking service – complete booking workflow with hardened concurrency protection.

═══════════════════════════════════════════════════════════════════════════════
Concurrency design (Phase 2 – hardened)
═══════════════════════════════════════════════════════════════════════════════

Problem with the Phase-1 approach
──────────────────────────────────
Phase 1 used find_one_and_update with $setOnInsert + upsert=True.
When an expired lock document still exists (TTL daemon hasn't run yet),
find_one_and_update UPDATES the stale document rather than inserting.
$setOnInsert only fires on a true insert, so the new owner token is NOT
written – the caller believes it holds the lock but doesn't own it, and the
stale token still matches no request.  This is a silent race condition.

Replacement strategy
─────────────────────
Layer 1 – insert_one-based exclusive lock
  • First delete any provably-expired lock for this equipment (safe – the
    requesting process cannot be its owner since it doesn't have a valid token).
  • Then attempt insert_one of a new lock document with our fresh owner token.
  • If insert_one raises DuplicateKeyError the equipment is locked by someone
    else  →  return 409.
  • We hold the lock only while we also hold the matching owner token; release
    deletes by {equipment_id, token} so we cannot accidentally remove a lock
    placed by a different request.
  • The TTL index is a safety net against crash-left locks, NOT the primary
    guarantor of expiry.

Layer 2 – overlap re-check inside the lock
  • With the exclusive lock held, re-query bookings for overlapping intervals.
  • Conflict statuses: pending | approved | active.

Layer 3 – replica-set transactions (opt-in)
  • If the Flask app config sets MONGO_REPLICA_SET=true the service will wrap
    the [overlap-check → insert booking] pair in a MongoDB multi-document
    transaction.  On a standalone server the session is omitted.

Lock safety guarantees
──────────────────────
  ✓ Owner-token check prevents cross-request lock release.
  ✓ Stale locks are cleaned before acquisition, not relied upon for cleanup.
  ✓ TTL is a redundant backstop (30 s), not the primary mechanism.
  ✓ Lock is released in a finally block even on exception.
  ✓ Lock expiry is checked on release – if the lock already expired and was
    re-acquired by another request, we do NOT delete it (token mismatch).
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from flask import current_app
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure

from ..extensions import mongo
from ..models.booking import build_booking_doc, validate_booking_payload


_LOCK_TTL_SECONDS = 30          # safety backstop; normal path releases < 1 s
_CONFLICT_STATUSES = {"pending", "approved", "active"}


# ── Exceptions ─────────────────────────────────────────────────────────────────

class BookingError(Exception):
    """General booking error (400-level)."""


class ConflictError(BookingError):
    """Booking slot conflict or lock contention (409)."""


class NotFoundError(BookingError):
    """Resource not found (404)."""


# ── Lock helpers ───────────────────────────────────────────────────────────────

@contextmanager
def _equipment_lock(equipment_id: str):
    """
    Context manager that acquires an exclusive per-equipment lock via
    insert_one + DuplicateKeyError.

    Protocol
    --------
    1. Delete any demonstrably expired lock for this equipment_id (not ours,
       but already past its TTL – safe to remove as a pre-condition).
    2. Try insert_one({equipment_id, token, expires_at}).
       - On success: we own the lock.
       - On DuplicateKeyError: someone else holds a valid lock → raise ConflictError.
    3. Yield (caller executes critical section).
    4. In finally: delete the lock document matching both equipment_id AND token.
       If the token no longer matches (i.e. the TTL daemon already removed our
       lock and a new one was inserted), we safely skip deletion.
    """
    lock_token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    lock_expires = now + timedelta(seconds=_LOCK_TTL_SECONDS)
    oid = ObjectId(equipment_id)

    # Step 1 – evict any provably-expired lock (cleanup, not ownership proof)
    mongo.db.booking_locks.delete_one(
        {"equipment_id": oid, "expires_at": {"$lte": now}}
    )

    # Step 2 – check for a live lock before inserting (compatible with both
    # real MongoDB and mongomock which does not enforce unique indexes)
    existing = mongo.db.booking_locks.find_one(
        {"equipment_id": oid, "expires_at": {"$gt": now}}
    )
    if existing:
        raise ConflictError(
            "Another booking for this equipment is being processed. "
            "Please retry in a moment."
        )

    # Step 3 – attempt to insert our lock atomically
    # On real MongoDB the unique index provides an additional safety net
    # for the race window between the find_one and insert_one above.
    try:
        mongo.db.booking_locks.insert_one(
            {
                "equipment_id": oid,
                "token": lock_token,
                "expires_at": lock_expires,
                "created_at": now,
            }
        )
    except DuplicateKeyError:
        raise ConflictError(
            "Another booking for this equipment is being processed. "
            "Please retry in a moment."
        )

    try:
        yield
    finally:
        # Step 4 – release only if we still own the lock
        # (token mismatch means TTL evicted our lock – do NOT remove a new owner's lock)
        mongo.db.booking_locks.delete_one(
            {"equipment_id": oid, "token": lock_token}
        )


# ── Overlap check ──────────────────────────────────────────────────────────────

def _check_overlap(
    equipment_id: ObjectId,
    start: datetime,
    end: datetime,
    exclude_id=None,
    session=None,
) -> Optional[dict]:
    """
    Return the first conflicting booking document, or None.
    Conflict = another booking in _CONFLICT_STATUSES whose interval overlaps [start, end).
    Two intervals [a,b) and [c,d) overlap iff a < d AND c < b.
    """
    query: dict = {
        "equipment_id": equipment_id,
        "status": {"$in": list(_CONFLICT_STATUSES)},
        "start_time": {"$lt": end},
        "end_time": {"$gt": start},
    }
    if exclude_id:
        query["_id"] = {"$ne": exclude_id}

    kwargs = {}
    if session is not None:
        kwargs["session"] = session
    return mongo.db.bookings.find_one(query, **kwargs)


# ── Replica-set transaction helper ─────────────────────────────────────────────

def _use_transactions() -> bool:
    """True when the app is configured to use replica-set transactions."""
    try:
        return current_app.config.get("MONGO_REPLICA_SET", False)
    except RuntimeError:
        return False


# ── Core booking logic ─────────────────────────────────────────────────────────

def create_booking(
    student_id: str,
    equipment_id: str,
    start_time: datetime,
    end_time: datetime,
    purpose: str,
    department_id: str = None,
    project_title: str = None,
    project_description: str = None,
    project_deadline: datetime = None,
    faculty_id: str = None,
    project_request_id=None,
) -> dict:
    """
    Atomically create a booking for an equipment item.
    Raises BookingError / ConflictError on failure.
    Returns the inserted booking document.
    """
    # ── 1. Validate inputs ────────────────────────────────────────────────
    payload = {
        "equipment_id": equipment_id,
        "start_time": start_time,
        "end_time": end_time,
        "purpose": purpose,
    }
    errors = validate_booking_payload(payload)
    if errors:
        raise BookingError("; ".join(errors))

    if start_time <= datetime.now(timezone.utc):
        raise BookingError("start_time must be in the future")

    # ── 2. Equipment existence + availability ─────────────────────────────
    equip_oid = ObjectId(equipment_id)
    equipment = mongo.db.equipment.find_one({"_id": equip_oid})
    if not equipment:
        raise NotFoundError("Equipment not found")
    if equipment["status"] not in {"available", "booked"}:
        raise BookingError(
            f"Equipment is currently '{equipment['status']}' and cannot be booked"
        )
    if equipment.get("quantity_available", 0) < 1:
        raise ConflictError("No units of this equipment are available")

    # ── 3. Acquire per-equipment exclusive lock ───────────────────────────
    with _equipment_lock(equipment_id):
        # ── 4. Overlap-check + insert (optionally in a transaction) ───────
        lab_id = equipment.get("lab_id")
        dept_oid = ObjectId(department_id) if department_id else equipment.get("department_id")
        fac_oid = ObjectId(faculty_id) if faculty_id else None
        proj_oid = ObjectId(project_request_id) if project_request_id else None

        doc = build_booking_doc(
            student_id=ObjectId(student_id),
            equipment_id=equip_oid,
            lab_id=lab_id,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
            department_id=dept_oid,
            project_title=project_title,
            project_description=project_description,
            project_deadline=project_deadline,
            faculty_id=fac_oid,
            project_request_id=proj_oid,
        )

        if _use_transactions():
            doc = _create_booking_transactional(equip_oid, start_time, end_time, doc)
        else:
            # Standalone server path
            conflict = _check_overlap(equip_oid, start_time, end_time)
            if conflict:
                raise ConflictError(
                    _fmt_conflict_msg(conflict)
                )
            result = mongo.db.bookings.insert_one(doc)
            doc["_id"] = result.inserted_id

    return doc


def _create_booking_transactional(equip_oid, start_time, end_time, doc) -> dict:
    """Overlap-check + insert wrapped in a MongoDB session/transaction."""
    client = mongo.cx       # the underlying MongoClient
    with client.start_session() as session:
        with session.start_transaction():
            conflict = _check_overlap(equip_oid, start_time, end_time, session=session)
            if conflict:
                session.abort_transaction()
                raise ConflictError(_fmt_conflict_msg(conflict))
            result = mongo.db.bookings.insert_one(doc, session=session)
            doc["_id"] = result.inserted_id
    return doc


def _fmt_conflict_msg(conflict: dict) -> str:
    cs = conflict["start_time"].strftime("%Y-%m-%d %H:%M UTC")
    ce = conflict["end_time"].strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Slot conflicts with an existing booking "
        f"({cs} – {ce}, status: {conflict['status']})"
    )


def approve_booking(booking_id: str, approver_id: str, notes: str = "") -> dict:
    """
    Approve a pending booking.
    Re-checks overlap against already-approved/active bookings before committing.
    """
    booking = _get_booking_or_raise(booking_id)
    if booking["status"] != "pending":
        raise BookingError(f"Cannot approve a booking with status '{booking['status']}'")

    # Re-check: only fail if conflicting booking is ALREADY approved/active
    # (pending vs pending conflict is handled at creation time)
    conflict = _check_overlap(
        booking["equipment_id"],
        booking["start_time"],
        booking["end_time"],
        exclude_id=booking["_id"],
    )
    if conflict and conflict["status"] in {"approved", "active"}:
        raise ConflictError(
            f"Cannot approve: conflicts with an already-approved booking "
            f"({conflict['start_time'].strftime('%Y-%m-%d %H:%M UTC')} – "
            f"{conflict['end_time'].strftime('%Y-%m-%d %H:%M UTC')})"
        )

    now = datetime.now(timezone.utc)
    mongo.db.bookings.update_one(
        {"_id": booking["_id"]},
        {
            "$set": {
                "status": "approved",
                "approved_by": ObjectId(approver_id),
                "approval_notes": (notes or "").strip(),
                "updated_at": now,
            }
        },
    )
    booking["status"] = "approved"
    booking["approval_notes"] = (notes or "").strip()
    return booking


def reject_booking(booking_id: str, approver_id: str, reason: str) -> dict:
    if not (reason or "").strip():
        raise BookingError("rejection_reason is required")
    booking = _get_booking_or_raise(booking_id)
    if booking["status"] not in {"pending"}:
        raise BookingError(f"Cannot reject a booking with status '{booking['status']}'")

    now = datetime.now(timezone.utc)
    mongo.db.bookings.update_one(
        {"_id": booking["_id"]},
        {
            "$set": {
                "status": "rejected",
                "approved_by": ObjectId(approver_id),
                "rejection_reason": reason.strip(),
                "updated_at": now,
            }
        },
    )
    booking["status"] = "rejected"
    booking["rejection_reason"] = reason.strip()
    return booking


def cancel_booking(booking_id: str, student_id: str) -> dict:
    booking = _get_booking_or_raise(booking_id)
    if str(booking["student_id"]) != student_id:
        raise BookingError("You can only cancel your own bookings")
    if booking["status"] not in {"pending", "approved"}:
        raise BookingError(f"Cannot cancel a booking with status '{booking['status']}'")

    # Prevent cancellation within 1 hour of start
    # Normalize to UTC-aware for comparison (mongomock may store naive datetimes)
    start = booking["start_time"]
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start <= datetime.now(timezone.utc) + timedelta(hours=1):
        raise BookingError("Cannot cancel a booking that starts within 1 hour")

    now = datetime.now(timezone.utc)
    mongo.db.bookings.update_one(
        {"_id": booking["_id"]},
        {"$set": {"status": "cancelled", "updated_at": now}},
    )
    booking["status"] = "cancelled"
    return booking


def get_availability(
    equipment_id: str,
    range_start: datetime,
    range_end: datetime,
) -> list[dict]:
    """Return all conflict-status bookings for an equipment in a date range, sorted by start_time."""
    equip_oid = ObjectId(equipment_id)
    return list(
        mongo.db.bookings.find(
            {
                "equipment_id": equip_oid,
                "status": {"$in": list(_CONFLICT_STATUSES)},
                "start_time": {"$lt": range_end},
                "end_time": {"$gt": range_start},
            }
        ).sort("start_time", ASCENDING)
    )


def list_bookings(
    student_id: str = None,
    equipment_id: str = None,
    status: str = None,
    limit: int = 20,
    after_id: str = None,
) -> dict:
    """
    Cursor-based paginated booking list.
    Returns {"items": [...], "next_cursor": str|None}.
    """
    limit = min(max(1, limit), 100)
    query: dict = {}
    if student_id:
        query["student_id"] = ObjectId(student_id)
    if equipment_id:
        query["equipment_id"] = ObjectId(equipment_id)
    if status:
        query["status"] = status
    if after_id:
        try:
            query["_id"] = {"$gt": ObjectId(after_id)}
        except Exception:
            pass

    items = list(
        mongo.db.bookings.find(query)
        .sort("_id", ASCENDING)
        .limit(limit + 1)
    )
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    next_cursor = str(items[-1]["_id"]) if has_more else None
    return {"items": items, "next_cursor": next_cursor}


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_booking_or_raise(booking_id: str) -> dict:
    try:
        oid = ObjectId(booking_id)
    except Exception:
        raise NotFoundError("Invalid booking ID")
    booking = mongo.db.bookings.find_one({"_id": oid})
    if not booking:
        raise NotFoundError("Booking not found")
    return booking
