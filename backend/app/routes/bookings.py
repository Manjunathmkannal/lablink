"""
/api/bookings  –  full booking CRUD + faculty approval/rejection workflow
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from bson import ObjectId

from ..utils.jwt_utils import jwt_required, role_required
from ..utils.json_utils import mongo_to_json
from ..extensions import mongo
from ..services.booking_service import (
    create_booking,
    approve_booking,
    reject_booking,
    cancel_booking,
    list_bookings,
    _get_booking_or_raise,
    BookingError,
    ConflictError,
    NotFoundError,
)
from ..services.notification_service import create_notification

bookings_bp = Blueprint("bookings", __name__)


def _parse_dt(val: str) -> datetime:
    """Parse ISO-8601 datetime string → UTC-aware datetime. Raises ValueError on failure."""
    if not val:
        raise ValueError("datetime value is empty")
    # Accept strings with or without 'Z' suffix
    val = val.replace("Z", "+00:00")
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        # Treat naive datetimes as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── GET /api/bookings  ─────────────────────────────────────────────────────────
@bookings_bp.route("/", methods=["GET"])
@jwt_required
def list_bk():
    """
    Cursor-based paginated booking list.
    Query params: status, equipment_id, limit (default 20), after (cursor ID).
    Students see only their own bookings. Faculty/Admin see all (or filter by student_id).
    """
    args = request.args
    role = g.current_role
    uid = g.current_user_id

    student_id_filter = None
    if role == "student":
        student_id_filter = uid   # students always see only their own
    elif args.get("student_id"):
        student_id_filter = args.get("student_id")

    result = list_bookings(
        student_id=student_id_filter,
        equipment_id=args.get("equipment_id", ""),
        status=args.get("status", ""),
        limit=int(args.get("limit", 20)),
        after_id=args.get("after", ""),
    )
    return jsonify(mongo_to_json(result))


# ── GET /api/bookings/<id>  ────────────────────────────────────────────────────
@bookings_bp.route("/<booking_id>", methods=["GET"])
@jwt_required
def get_bk(booking_id):
    try:
        booking = _get_booking_or_raise(booking_id)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404

    # Students can only see their own bookings
    if g.current_role == "student" and str(booking["student_id"]) != g.current_user_id:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify(mongo_to_json(booking))


# ── POST /api/bookings  ────────────────────────────────────────────────────────
@bookings_bp.route("/", methods=["POST"])
@jwt_required
@role_required("student")
def create_bk():
    """Create a new booking request (students only)."""
    data = request.get_json(silent=True) or {}

    # Parse datetimes
    try:
        start_time = _parse_dt(data.get("start_time", ""))
        end_time = _parse_dt(data.get("end_time", ""))
    except ValueError as e:
        return jsonify({"error": f"Invalid datetime: {e}"}), 400

    project_deadline = None
    if data.get("project_deadline"):
        try:
            project_deadline = _parse_dt(data["project_deadline"])
        except ValueError:
            return jsonify({"error": "Invalid project_deadline format"}), 400

    try:
        booking = create_booking(
            student_id=g.current_user_id,
            equipment_id=data.get("equipment_id", ""),
            start_time=start_time,
            end_time=end_time,
            purpose=data.get("purpose", ""),
            department_id=data.get("department_id"),
            project_title=data.get("project_title"),
            project_description=data.get("project_description"),
            project_deadline=project_deadline,
            faculty_id=data.get("faculty_id"),
        )
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except BookingError as e:
        return jsonify({"error": str(e)}), 400

    # Notify the student that their request was submitted
    create_notification(
        user_id=g.current_user_id,
        notif_type="system",
        title="Booking request submitted",
        message=f"Your booking request for equipment has been submitted and is pending approval.",
        reference_id=booking["_id"],
        reference_type="booking",
    )

    # Notify faculty if a faculty_id was specified
    if booking.get("faculty_id"):
        create_notification(
            user_id=booking["faculty_id"],
            notif_type="system",
            title="New booking request requires your approval",
            message=f"A student has submitted a booking request that requires your approval.",
            reference_id=booking["_id"],
            reference_type="booking",
        )

    return jsonify({"message": "Booking request created", "booking": mongo_to_json(booking)}), 201


# ── PUT /api/bookings/<id>/approve  ───────────────────────────────────────────
@bookings_bp.route("/<booking_id>/approve", methods=["PUT"])
@jwt_required
@role_required("faculty", "admin")
def approve_bk(booking_id):
    """Approve a pending booking (faculty/admin only)."""
    data = request.get_json(silent=True) or {}
    notes = data.get("notes", "")

    try:
        booking = approve_booking(booking_id, g.current_user_id, notes)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ConflictError as e:
        return jsonify({"error": str(e)}), 409
    except BookingError as e:
        return jsonify({"error": str(e)}), 400

    # Notify the student
    create_notification(
        user_id=str(booking["student_id"]),
        notif_type="booking_approved",
        title="Booking approved",
        message=f"Your booking request has been approved.",
        reference_id=booking["_id"],
        reference_type="booking",
    )

    return jsonify({"message": "Booking approved", "booking": mongo_to_json(booking)})


# ── PUT /api/bookings/<id>/reject  ────────────────────────────────────────────
@bookings_bp.route("/<booking_id>/reject", methods=["PUT"])
@jwt_required
@role_required("faculty", "admin")
def reject_bk(booking_id):
    """Reject a pending booking with a mandatory reason."""
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or data.get("rejection_reason") or "").strip()
    if not reason:
        return jsonify({"error": "rejection_reason is required"}), 400

    try:
        booking = reject_booking(booking_id, g.current_user_id, reason)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except BookingError as e:
        return jsonify({"error": str(e)}), 400

    # Notify the student
    create_notification(
        user_id=str(booking["student_id"]),
        notif_type="booking_rejected",
        title="Booking rejected",
        message=f"Your booking request was rejected. Reason: {reason}",
        reference_id=booking["_id"],
        reference_type="booking",
    )

    return jsonify({"message": "Booking rejected", "booking": mongo_to_json(booking)})


# ── PUT /api/bookings/<id>/cancel  ────────────────────────────────────────────
@bookings_bp.route("/<booking_id>/cancel", methods=["PUT"])
@jwt_required
def cancel_bk(booking_id):
    """Cancel a booking. Students cancel their own; admin can cancel any."""
    role = g.current_role
    uid = g.current_user_id

    try:
        booking = _get_booking_or_raise(booking_id)
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404

    # Permission check
    is_own = str(booking["student_id"]) == uid
    if role == "student" and not is_own:
        return jsonify({"error": "Forbidden: you can only cancel your own bookings"}), 403

    if role == "admin":
        # Admin can cancel any pending/approved booking without the 1-hour rule
        from ..services.booking_service import _get_booking_or_raise as _gbr
        from ..extensions import mongo as _mongo
        from datetime import datetime as _dt
        allowed = {"pending", "approved"}
        if booking["status"] not in allowed:
            return jsonify({"error": f"Cannot cancel a booking with status '{booking['status']}'"}), 400
        _mongo.db.bookings.update_one(
            {"_id": booking["_id"]},
            {"$set": {"status": "cancelled", "updated_at": _dt.now(timezone.utc)}},
        )
        booking["status"] = "cancelled"
    else:
        try:
            booking = cancel_booking(booking_id, uid)
        except BookingError as e:
            return jsonify({"error": str(e)}), 400

    # Notify the student if cancelled by admin
    if not is_own:
        create_notification(
            user_id=str(booking["student_id"]),
            notif_type="system",
            title="Booking cancelled",
            message="Your booking was cancelled by an administrator.",
            reference_id=booking["_id"],
            reference_type="booking",
        )
    else:
        create_notification(
            user_id=uid,
            notif_type="system",
            title="Booking cancelled",
            message="Your booking has been cancelled.",
            reference_id=booking["_id"],
            reference_type="booking",
        )

    return jsonify({"message": "Booking cancelled", "booking": mongo_to_json(booking)})
